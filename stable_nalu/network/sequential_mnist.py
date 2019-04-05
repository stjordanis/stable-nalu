
import torch
from ..layer import GeneralizedLayer, GeneralizedCell
from ..writer import DummyWriter

# Copied from https://github.com/pytorch/examples/blob/master/mnist/main.py, just added a
# reset_parameters method and changed log_softmax to softmax.

class _Image2LabelCNN(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = torch.nn.Conv2d(1, 20, 5, 1)
        self.conv2 = torch.nn.Conv2d(20, 50, 5, 1)
        self.fc1 = torch.nn.Linear(4*4*50, 500)
        self.fc2 = torch.nn.Linear(500, 10)

    def reset_parameters(self):
        self.conv1.reset_parameters()
        self.conv2.reset_parameters()
        self.fc1.reset_parameters()
        self.fc2.reset_parameters()

    def forward(self, x):
        x = torch.nn.functional.relu(self.conv1(x))
        x = torch.nn.functional.max_pool2d(x, 2, 2)
        x = torch.nn.functional.relu(self.conv2(x))
        x = torch.nn.functional.max_pool2d(x, 2, 2)
        x = x.view(-1, 4*4*50)
        x = torch.nn.functional.relu(self.fc1(x))
        return self.fc2(x)
        # return torch.nn.functional.softmax(x, dim=1)  # do we want a softmax?

class SequentialMnistNetwork(torch.nn.Module):
    def __init__(self, unit_name, output_size,
                 writer=DummyWriter(), **kwags):
        super().__init__()
        self.unit_name = unit_name
        self.output_size = output_size

        # TODO: maybe don't make them learnable, properly zero will surfise here
        if unit_name == 'LSTM':
            self.register_buffer('zero_state_h', torch.Tensor(self.output_size))
            self.register_buffer('zero_state_c', torch.Tensor(self.output_size))
        else:
            self.register_buffer('zero_state', torch.Tensor(self.output_size))

        self.image2label = _Image2LabelCNN()
        self.recurent_cell = GeneralizedCell(10, self.output_size,
                                             unit_name,
                                             writer=writer.namespace('recurrent_layer'),
                                             **kwags)

    def reset_parameters(self):
        if self.unit_name == 'LSTM':
            torch.nn.init.zeros_(self.zero_state_h)
            torch.nn.init.zeros_(self.zero_state_c)
        else:
            torch.nn.init.zeros_(self.zero_state)

        self.image2label.reset_parameters()
        self.recurent_cell.reset_parameters()

    def forward(self, x):
        """Performs recurrent iterations over the input.

        Arguments:
            input: Expected to have the shape [obs, time, channels=1, width, height]
        """
        # Perform recurrent iterations over the input
        if self.unit_name == 'LSTM':
            h_tm1 = (
                self.zero_state_h.repeat(x.size(0), 1),
                self.zero_state_c.repeat(x.size(0), 1)
            )
        else:
            h_tm1 = self.zero_state.repeat(x.size(0), 1)

        for t in range(x.size(1)):
            x_t = x[:, t]
            l_t = self.image2label(x_t)
            h_t = self.recurent_cell(l_t, h_tm1)
            h_tm1 = h_t

        # Grap the final hidden output and use as the output from the recurrent layer
        z_1 = h_t[0] if self.unit_name == 'LSTM' else h_t

        return z_1

    def extra_repr(self):
        return 'unit_name={}, output_size={}'.format(
            self.unit_name, self.output_size
        )
