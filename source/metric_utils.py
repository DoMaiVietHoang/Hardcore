#to build
# python3.10 setup.py build_ext --inplace


import numpy as np

def build_mul_matrix(matrix, indices):
    cols = len(indices)
    src_rows, src_cols = matrix.shape
    res_np = np.zeros((src_cols, cols), dtype=np.float32)
    
    for i, arr in enumerate(indices):
        for j in arr:
            res_np[j, i] = 1.0
    
    return res_np

def get_max_indices(matrix, indices):
    src_rows, src_cols = matrix.shape
    res = np.zeros((src_rows, len(indices)), dtype=np.int64)
    
    for r in range(src_rows):
        for i, arr in enumerate(indices):
            max_v = -9999
            max_i = -1
            for i2 in arr:
                if matrix[r, i2] > max_v:
                    max_v = matrix[r, i2]
                    max_i = i2 + r * src_cols
            
            res[r, i] = max_i
    
    return res

def cal_hierarchical_sum(matrix, indices, rule='max'):
    cols = len(indices)
    rows = matrix.shape[0]
    res = np.zeros((rows, cols), dtype=np.float32)
    
    for r in range(rows):
        for i, arr in enumerate(indices):
            s = 0.0
            for item in arr:
                if rule == 'sum':
                    s += matrix[r, item]
                elif rule == 'max':
                    if matrix[r, item] > s:
                        s = matrix[r, item]
            
            res[r, i] = s
    
    return res

    # cdef np.float32_t sum_val = 0.0
    # cdef Py_ssize_t i, j
    # cdef Py_ssize_t rows = matrix.shape[0]
    # cdef Py_ssize_t cols = matrix.shape[1]
    # cdf int
    # for i in range(rows):
    #     for j in range(cols):
    #         sum_val += matrix[i, j]

    # return sum_val
