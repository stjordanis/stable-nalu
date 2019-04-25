
import torch

from ..abstract import ExtendedTorchModule

torch.nn.functional.gumbel_softmax

class AbstractNALULayer(ExtendedTorchModule):
    """Implements the NALU (Neural Arithmetic Logic Unit)

    Arguments:
        in_features: number of ingoing features
        out_features: number of outgoing features
    """

    def __init__(self, NACOp, in_features, out_features, eps=1e-7,
                 nalu_two_nac=False, nalu_bias=False, nalu_mul='normal', nalu_gate='normal',
                 writer=None, name=None, **kwargs):
        super().__init__('nalu', name=name, writer=writer, **kwargs)
        self.in_features = in_features
        self.out_features = out_features
        self.eps = eps
        self.nalu_two_nac = nalu_two_nac
        self.nalu_bias = nalu_bias
        self.nalu_mul = nalu_mul
        self.nalu_gate = nalu_gate

        if nalu_gate == 'gumbel' or nalu_gate == 'obs-gumbel':
            self.tau = torch.tensor(1, dtype=torch.float32)

        if nalu_two_nac:
            self.nac_add = NACOp(in_features, out_features, writer=self.writer, name='nac_add', **kwargs)
            self.nac_mul = NACOp(in_features, out_features, writer=self.writer, name='nac_mul', **kwargs)
        else:
            self.nac_add = NACOp(in_features, out_features, writer=self.writer, **kwargs)
            self.nac_mul = lambda x: self.nac_add(x, reuse=True)

        self.G = torch.nn.Parameter(torch.Tensor(out_features, in_features))

        if nalu_bias:
            self.bias = torch.nn.Parameter(torch.Tensor(out_features))
        else:
            self.register_parameter('bias', None)

        # Don't make this a buffer, as it is not a state that we want to permanently save
        self.stored_gate = torch.tensor([0], dtype=torch.float32)

    def regualizer(self):
        if self.nalu_gate == 'regualized':
            # NOTE: This is almost identical to sum(g * (1 - g)). Primarily
            # sum(g * (1 - g)) is 4 times larger than sum(g^2 * (1 - g)^2), the curve
            # is also a bit wider. Besides this there is only a very small error.
            regualizer = torch.sum(self.stored_gate**2 * (1 - self.stored_gate)**2)
            self.writer.add_scalar('regualizer', regualizer)
        else:
            regualizer = 0

        # Continue recursion on the regualizer, such that if the NACOp has a regualizer, this is included too.
        return regualizer + super().regualizer()

    def reset_parameters(self):
        if self.nalu_two_nac:
            self.nac_add.reset_parameters()
            self.nac_mul.reset_parameters()
        else:
            self.nac_add.reset_parameters()

        torch.nn.init.xavier_uniform_(
            self.G,
            gain=torch.nn.init.calculate_gain('sigmoid'))

        if self.nalu_bias:
            # consider http://proceedings.mlr.press/v37/jozefowicz15.pdf
            torch.nn.init.zeros_(self.bias)

    def forward(self, x):
        # g = sigmoid(G x)
        if self.nalu_gate == 'gumbel' or self.nalu_gate == 'obs-gumbel':
            gumbel = 0
            if self.allow_random and self.nalu_gate == 'gumbel':
                gumbel = (-torch.log(1e-8 - torch.log(torch.rand(self.out_features, device=x.device) + 1e-8)))
            elif self.allow_random and self.nalu_gate == 'obs-gumbel':
                gumbel = (-torch.log(1e-8 - torch.log(torch.rand(x.size(0), self.out_features, device=x.device) + 1e-8)))

            g = torch.sigmoid((torch.nn.functional.linear(x, self.G, self.bias) + gumbel) / self.tau)
        else:
            g = torch.sigmoid(torch.nn.functional.linear(x, self.G, self.bias))

        self.stored_gate = g
        self.writer.add_histogram('gate', g)
        # a = W x = nac(x)
        a = self.nac_add(x)
        # m = exp(W log(|x| + eps)) = exp(nac(log(|x| + eps)))
        if self.nalu_mul == 'safe':
            m = torch.exp(self.nac_mul(
                torch.log(torch.abs(x - 1) + 1)
            ))
        elif self.nalu_mul == 'trig':
            m = torch.sinh(self.nac_mul(
                torch.log(x+(x**2+1)**0.5 + self.eps)  # torch.asinh(x) does not exist
            ))
        else:
            m = torch.exp(self.nac_mul(
                torch.log(torch.abs(x) + self.eps)
            ))

        self.writer.add_histogram('add', a)
        self.writer.add_histogram('mul', m)
        # y = g (*) a + (1 - g) (*) m
        y = g * a + (1 - g) * m

        return y

    def extra_repr(self):
        return 'in_features={}, out_features={}, eps={}, nalu_two_nac={}, nalu_bias={}'.format(
            self.in_features, self.out_features, self.eps, self.nalu_two_nac, self.nalu_bias
        )
