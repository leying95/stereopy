#!/usr/bin/env python3
# coding: utf-8
"""
@author: Ping Qiu  qiuping1@genomics.cn
@last modified by: Ping Qiu
@file:stereo_result.py
@time:2021/03/18
"""
from typing import Optional
import numpy as np
import pandas as pd
from ..log_manager import logger


class StereoResult(object):
    def __init__(self, name: str = 'stereo', param: Optional[dict] = None):
        self.name = name
        self.params = {} if param is None else param

    def update_params(self, v):
        self.params = v

    def __str__(self):
        class_info = f'{self.__class__.__name__} of {self.name}. \n'
        class_info += f'  params: {self.params}\n'
        return class_info

    def __repr__(self):
        return self.__str__()


class DimReduceResult(StereoResult):
    def __init__(self, name: str = 'dim_reduce', param: Optional[dict] = None, x_reduce: Optional[np.ndarray] = None,
                 variance_pca: Optional[np.ndarray] = None, variance_ratio: Optional[np.ndarray] = None,
                 pcs: Optional[np.ndarray] = None):
        super(DimReduceResult, self).__init__(name, param)
        self.x_reduce = x_reduce
        self.variance_pca = variance_pca
        self.variance_ratio = variance_ratio
        self.pcs = pcs


class FindMarkerResult(StereoResult):
    def __init__(self, name: str = 'find_marker', param: Optional[dict] = None,
                 degs_data: Optional[pd.DataFrame] = None):
        super(FindMarkerResult, self).__init__(name, param)
        self.degs_data = degs_data

    def __str__(self):
        info = super(FindMarkerResult, self).__str__()
        if self.degs_data is not None:
            info += f'    result: a DataFrame which has `genes`,`pvalues`,`pvalues_adj`, `log2fc`, `score` columns.\n'
            info += f'    the shape is: {self.degs_data.shape}'
        return info

    def top_k_marker(self, top_k_genes=10, sort_key='pvalues', ascend=False):
        """
        obtain the first k significantly different genes
        :param top_k_genes:  the number of top k
        :param sort_key: sort by the column
        :param ascend: the ascend order of sorting.
        :return:
        """
        if self.degs_data is not None:
            top_k_data = self.degs_data.sort_values(by=sort_key, ascending=ascend).head(top_k_genes)
            return top_k_data
        else:
            logger.warning('the result of degs is None, return None.')
            return None


class CellTypeResult(StereoResult):
    def __init__(self, name='cell_type_anno', param=None, anno_data=None):
        super(CellTypeResult, self).__init__(name=name, param=param)
        self.anno_data = anno_data

    def __str__(self):
        info = super(CellTypeResult, self).__str__()
        if self.anno_data is not None:
            info += f'    result: a DataFrame which has `cells`,`cell type`,`corr_score` columns.\n'
            info += f'    the shape is: {self.anno_data.shape}'
        return info


class ClusterResult(StereoResult):
    def __init__(self, name='cluster', param=None, cluster_info=None):
        super(ClusterResult, self).__init__(name=name, param=param)
        self.cluster = cluster_info

    def __str__(self):
        info = super(ClusterResult, self).__str__()
        if self.cluster is not None:
            info += f'    result: a DataFrame which has `cells`,`cluster` columns.\n'
            info += f'    the shape is: {self.cluster.shape}'
        return info
