#!/usr/bin/env python3
# coding: utf-8
"""
@author: Ping Qiu  qiuping1@genomics.cn
@last modified by: Ping Qiu
@file:cell_type_anno.py
@time:2021/03/09
"""
import pandas as pd
import numpy as np
import os
from multiprocessing import Pool
import traceback
from ..log_manager import logger
from ..utils.correlation import spearmanr_corr, pearson_corr
from ..preprocess.normalize import normalize_total
from ..config import stereo_conf
from ..utils import remove_file
from ..core.tool_base import ToolBase
from ..core.stereo_result import CellTypeResult
from scipy.sparse import issparse


class CellTypeAnno(ToolBase):
    def __init__(self, adata, ref_dir=None, cores=1, keep_zeros=True, use_rf=True, sample_rate=0.8,
                 n_estimators=20, strategy='1', method='spearmanr', split_num=1, out_dir=None, name='cell_type_anno'):
        super(CellTypeAnno, self).__init__(data=adata, method=method, name=name)
        self.param = locals()
        self.data = adata
        self.ref_dir = ref_dir if ref_dir else os.path.join(stereo_conf.data_dir, 'ref_db', 'FANTOM5')
        self.n_jobs = cores
        self.keep_zeros = keep_zeros
        self.use_rf = use_rf
        self.sample_rate = sample_rate
        self.n_estimators = n_estimators
        self.strategy = strategy
        self.method = method
        self.split_num = split_num
        self.output = out_dir if out_dir else stereo_conf.out_dir
        self.result = CellTypeResult(name=name, param=self.param)
        self.check_param()

    def split_dataframe(self, df):

        datas = []
        logger.info(f'input data:  {df.shape[0]} genes, {df.shape[1]} cells.')
        if self.split_num > 1:
            logger.info(f'split the anndata.X to {self.split_num} matrixs')
            step_size = int(df.shape[1]/self.split_num) + 1
            for i in range(self.split_num):
                start = i * step_size
                end = start + step_size if start + step_size < df.shape[1] else df.shape[1]
                datas.append(df.iloc[:, start: end])
        else:
            datas.append(df)
        return datas

    @staticmethod
    def concat_top_corr_files(files, output_dir, prefix=None):
        df = pd.read_csv(files[0])
        for f in files[1:]:
            df1 = pd.read_csv(f)
            df = df.append(df1)
        file_name = f'{prefix}_top_annotation.csv' if prefix else 'top_annotation.csv'
        df.to_csv(os.path.join(output_dir, file_name), index=False)
        return df

    def merge_subsample_result(self, input_dir, prefix, output_dir):
        files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if prefix in f]
        df = pd.read_csv(files[0])
        for f in files[1:]:
            df1 = pd.read_csv(f)
            df = df.append(df1)
        type_cnt = df.groupby(['cell', 'cell type']).count()[['corr_score']]
        type_cnt['type_rate'] = type_cnt / self.n_estimators
        type_cnt.columns = ['type_cnt', 'type_rate']
        type_cnt.reset_index(inplace=True)
        score_mean = df.groupby(['cell', 'cell type']).mean()[['corr_score']]
        score_mean.columns = ['score_mean']
        score_mean.reset_index(inplace=True)
        df = score_mean.merge(type_cnt, on=['cell', 'cell type'])
        df.to_csv(os.path.join(output_dir, 'all_annotation.csv'), index=False)
        df = df[(df.groupby('cell')['type_cnt'].transform('max') == df['type_cnt']) & (
                    df.groupby('cell')['score_mean'].transform('max') == df['score_mean'])]
        df.to_csv(os.path.join(output_dir, 'top_annotation.csv'), index=False)
        return df

    @staticmethod
    def merge_subsample_result_filter(input_dir, prefix, output_dir):
        files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if prefix in f]
        df = pd.read_csv(files[0])
        for f in files[1:]:
            df_1 = pd.read_csv(f)
            df = df.append(df_1)
        score_mean = df.groupby(['cell', 'cell type']).mean()[['corr_score']]
        score_mean.columns = ['score_mean']
        score_mean.reset_index(inplace=True)
        tmp = score_mean.merge(df, on=['cell', 'cell type'])
        tmp = tmp[tmp['score_mean'] <= tmp['corr_score']]
        type_cnt = tmp.groupby(['cell', 'cell type']).count()[['score_mean']].reset_index()
        type_sum = tmp.groupby(['cell']).count()[['corr_score']].reset_index()
        score_mean = tmp.groupby(['cell', 'cell type']).mean()[['corr_score']]
        score_mean.columns = ['score_mean']
        score_mean.reset_index(inplace=True)
        type_rate = type_cnt.merge(type_sum, on=['cell'])
        type_rate['type_rate'] = type_rate['score_mean'] / type_rate['corr_score']
        type_rate.columns = ['cell', 'cell type', 'type_cnt', 'type_cnt_sum', 'type_rate']
        df = score_mean.merge(type_rate, on=['cell', 'cell type'])
        df.to_csv(os.path.join(output_dir, 'all_annotation.csv'), index=False)
        df = df[df.groupby('cell')['type_cnt'].transform('max') == df['type_cnt']]
        df = df[df.groupby('cell')['score_mean'].transform('max') == df['score_mean']]
        df.to_csv(os.path.join(output_dir, 'top_annotation.csv'), index=False)
        return df

    def fit(self):
        exp_matrix = self.data.X.toarray().T if issparse(self.data.X) else self.data.X.T
        df = pd.DataFrame(exp_matrix, index=list(self.data.var_names),
                          columns=list(self.data.obs_names))
        datas = self.split_dataframe(df) if self.split_num > 1 else [df]
        tmp_output = os.path.join(self.output, 'tmp')
        logger.info('start to run annotation.')
        if not os.path.exists(tmp_output):
            os.makedirs(tmp_output)
        if self.use_rf:
            pool = Pool(self.n_jobs)
            for i in range(self.n_estimators):
                for j in range(len(datas)):
                    sub_index = f'subsample_{i}_{j}'
                    pool.apply_async(run_annotation, (datas[j], self.ref_dir, self.method, self.keep_zeros, tmp_output,
                                                      sub_index, self.use_rf, self.sample_rate),
                                     error_callback=subprocess_error)
            pool.close()
            pool.join()
            logger.info(f'start to merge top result ...')
            for i in range(self.n_estimators):
                files = [os.path.join(tmp_output, f'subsample_{i}_{j}.top_{self.method}_corr.csv')
                         for j in range(self.split_num)]
                index = f'subsample_{i}'
                self.concat_top_corr_files(files, tmp_output, index)
            if self.strategy == 1:
                self.result.anno_data = self.merge_subsample_result(tmp_output, 'top_annotation.csv', self.output)
            else:
                self.result.anno_data = self.merge_subsample_result_filter(tmp_output, 'top_annotation.csv',
                                                                           self.output)
        else:
            pool = Pool(self.n_jobs)
            for i in range(len(datas)):
                sub_index = f'sub_{i}'
                pool.apply_async(run_annotation, (datas[i], self.ref_dir, self.method, self.keep_zeros, tmp_output,
                                                  sub_index, self.use_rf, self.sample_rate),
                                 error_callback=subprocess_error)
            pool.close()
            pool.join()
            logger.info(f'start to merge top result ...')
            files = [os.path.join(tmp_output, f'sub_{i}.top_{self.method}_corr.csv') for i in range(len(datas))]
            self.result.anno_data = self.concat_top_corr_files(files, self.output)
        # clear tmp directory
        remove_file(tmp_output)
        self.add_result(result=self.result, key_added=self.name)


def parse_ref_data(ref_dir):
    logger.info(f'loading ref data')
    ref_sample_path = os.path.join(ref_dir, 'ref_sample_epx.csv')
    ref_db = pd.read_csv(ref_sample_path, index_col=0, header=0)
    ref_db = ref_db.fillna(0)
    # remove duplicate indices
    ref_db = ref_db[~ref_db.index.duplicated(keep='first')]
    logger.info('reference dataset shape: %s genes, %s samples' % ref_db.shape)
    return ref_db


def random_choose_genes(df, sample_rate):
    sample_cnt = pd.Series(np.int32(df.sum(axis=0) * sample_rate), index=df.columns)
    gene_rate = df / df.sum(axis=0)
    sample_df = gene_rate.apply(lambda x: choose_gene(x, sample_cnt), axis=0)
    sample_df.fillna(0, inplace=True)
    return sample_df


def choose_gene(x, num):
    gene_list = list(x.index)
    p = x.values
    res = np.random.choice(a=gene_list, size=num[x.name], p=p)
    res = np.unique(res, return_counts=True)
    res = pd.Series(data=res[1], index=res[0], name=x.name)
    return res


def annotation(df, ref_db, method, keep_zeros):
    # find common genes between test data and ref data
    test_genes = set(df.index)
    ref_genes = set(ref_db.index)
    if keep_zeros:
        common_genes = list(ref_genes)
    else:
        common_genes = list(ref_genes.intersection(test_genes))
    # only keep non-zero genes
    df = df.reindex(common_genes, fill_value=0.0)
    ref_db = ref_db.reindex(common_genes, fill_value=0.0)
    if method == 'pearson':
        corr_score = pearson_corr(ref_db, df)
    else:
        corr_score = spearmanr_corr(ref_db, df)
    corr_score = corr_score.fillna(0)
    return corr_score


def get_top_corr(score, cell_map, output):
    max_index = score.values.argmax(axis=1)
    max_value = score.values.max(axis=1)
    samples = score.columns[max_index]
    cell_type = cell_map.loc[samples, 'cell type']
    cell = score.index
    df = pd.DataFrame({'cell': cell, 'cell type': cell_type, 'corr_score': max_value, 'corr_sample': samples})
    df.to_csv(output, index=False)
    return df


def run_annotation(sub_df, ref_dir, method, keep_zero, output, sub_index, use_rf, sample_rate):
    ref_db = parse_ref_data(ref_dir)
    cell_map = pd.read_csv(os.path.join(ref_dir, 'cell_map.csv'), index_col=0, header=0, sep=',')
    if use_rf:
        logger.info('random choose')
        sub_df = random_choose_genes(sub_df, sample_rate)
    nor_x = normalize_total(sub_df.transpose().values, target_sum=10000)  # TODO  select some of normalize method
    nor_x = np.log1p(nor_x, out=nor_x)
    sub_df = pd.DataFrame(nor_x.T, columns=sub_df.columns, index=sub_df.index)
    logger.info('annotation')
    corr_df = annotation(sub_df, ref_db, method, keep_zero)
    all_out = os.path.join(output, f'{sub_index}.all_{method}_corr.csv')
    top_out = os.path.join(output, f'{sub_index}.top_{method}_corr.csv')
    corr_df.to_csv(all_out)
    get_top_corr(corr_df, cell_map, top_out)
    logger.info(f'subsample {sub_index} DONE!')


def subprocess_error(value):
    """
    子进程打印错误信息
    :param value:
    :return:
    """
    logger.error(f"error: {value}")
    logger.error("========")
    logger.error(traceback.format_exc())
    raise
