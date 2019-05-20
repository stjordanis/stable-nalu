
job_name='sequential_mnist_csv_metrics'
experiment_names=( 'sequential_mnist_sum' 'sequential_mnist_prod' )

for experiment_name in "${experiment_names[@]}"
do
    bsub -q compute -n 16 -W 3:00 -J ${job_name} -o /work3/$USER/logs/${job_name}/ -e /work3/$USER/logs/${job_name}/ -R "span[hosts=1]" -R "rusage[mem=10GB]" ./python_lfs_job.sh \
        export/sequential_mnist.py \
        --tensorboard-dir /work3/$USER/tensorboard/${experiment_name}/ \
        --csv-out ./results/${experiment_name}.csv
done