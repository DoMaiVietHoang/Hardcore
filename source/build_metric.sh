# python3.10-config --ldflags
# python3.10-configmetrics_util--includes
# python3.10 -c "import numpy; print(numpy.get_include())"
gcc -shared -o example.pyd metrics_util.c -I /usr/local/include/python3.10 -I /media/data3/home/namhv/.local/lib/python3.6/site-packages/numpy/core/include -L /usr/local/lib/python3.10/config-3.10-x86_64-linux-gnu -lpython3.10
