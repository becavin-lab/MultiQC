#!/usr/bin/env python

""" MultiQC module to parse output from checkatlas """

from __future__ import print_function

import math
import shutil

import os.path
from collections import OrderedDict
import logging
import re
from multiqc import config
from multiqc.plots import table, linegraph
from multiqc.modules.base_module import BaseMultiqcModule

# Initialise the logger
log = logging.getLogger(__name__)

FIG_PATH = "checkatlas_fig"

QC_HEADER = ["total_counts", "n_genes_by_counts", "pct_counts_mt"]

LIST_PATTERN = [
    "checkatlas/summary",
    "checkatlas/adata",
    "checkatlas/qc",
    "checkatlas/umap",
    "checkatlas/tsne",
    "checkatlas/cluster",
    "checkatlas/annotation",
    "checkatlas/dimred",
    "checkatlas/specificity",
]

DICT_EXTENSION = {
    "checkatlas/summary": "_checkatlas_summ.tsv",
    "checkatlas/adata": "_checkatlas_adata.tsv",
    "checkatlas/qc": "_checkatlas_qc.png",
    "checkatlas/umap": "_checkatlas_umap.png",
    "checkatlas/tsne": "_checkatlas_tsne.png",
    "checkatlas/cluster": "_checkatlas_mcluster.tsv",
    "checkatlas/annotation": "_checkatlas_mannot.tsv",
    "checkatlas/dimred": "_checkatlas_mdimred.tsv",
    "checkatlas/specificity": "_checkatlas_mspecificity.tsv",
}

DICT_NAMING = {
    "checkatlas/summary": "checkatlas_summ",
    "checkatlas/adata": "_checkatlas_adata",
    "checkatlas/qc_fig": "checkatlas_qc_fig",
    "checkatlas/qc": "checkatlas_qc",
    "checkatlas/umap": "_checkatlas_umap",
    "checkatlas/tsne": "checkatlas_tsne",
    "checkatlas/cluster": "_checkatlas_mcluster",
    "checkatlas/annotation": "checkatlas_mannot",
    "checkatlas/dimred": "_checkatlas_mdimred",
    "checkatlas/specificity": "checkatlas_mspecificity",
}


openpng_html_script = """
        <script>
        function openPNG(evt, pngName, tablinks_id, tabcontent_id) {
          var i, tabcontent, tablinks;
          tabcontent = document.getElementsByClassName(tabcontent_id);
          for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none";
          }
          tablinks = document.getElementsByClassName(tablinks_id);
          for (i = 0; i < tablinks.length; i++) {
            tablinks[i].className = tablinks[i].className.replace(" active", "");
          }
          document.getElementById(pngName).style.display = "block";
          evt.currentTarget.className += " active";
        }
        </script>
        """


class MultiqcModule(BaseMultiqcModule):
    """checkatlas module, parses stderr logs."""

    def __init__(self):

        fig_dir = os.path.join(config.data_dir, FIG_PATH)
        os.mkdir(fig_dir)

        # Initialise the parent object
        super(MultiqcModule, self).__init__(
            name="CheckAtlas",
            anchor="checkatlas",
            href="https://github.com/becavin-lab/checkatlas",
            info="A one-liner tool for quality control of your single-cell atlases.",
            doi="",
        )

        self.data_summary = dict()
        for f in self.find_log_files("checkatlas/summary"):
            input_fname = f["s_name"].replace("_checkatlas_summ", "")
            s_name = self.clean_s_name(input_fname, f)
            self.data_summary[s_name] = parse_firstline_table_logs(f["f"])
            self.add_data_source(f, s_name)

        self.data_adata = dict()
        for f in self.find_log_files("checkatlas/adata"):
            input_fname = f["s_name"].replace("_checkatlas_adata", "")
            s_name = self.clean_s_name(input_fname, f)
            self.data_adata[s_name] = parse_firstline_table_logs(f["f"])
            self.add_data_source(f, s_name)

        self.data_qc_fig = dict()
        for f in self.find_log_files("checkatlas/qc_fig"):
            # copy figures to multiqc data folder
            shutil.copy2(os.path.join(f["root"], f["fn"]), fig_dir)
            input_fname = f["s_name"].replace("_checkatlas_qc", "")
            s_name = self.clean_s_name(input_fname, f)
            self.data_qc_fig[s_name] = f["fn"]
            self.add_data_source(f, s_name)

        self.data_qc_counts = dict()
        self.data_qc_genes = dict()
        self.data_qc_mito = dict()
        for f in self.find_log_files("checkatlas/qc"):
            input_fname = f["s_name"].replace("_checkatlas_qc", "")
            s_name = self.clean_s_name(input_fname, f)
            data_qc_counts, data_qc_genes, data_qc_mito = parse_qc_logs(f["f"])
            self.data_qc_counts[s_name] = data_qc_counts
            self.data_qc_genes[s_name] = data_qc_genes
            self.data_qc_mito[s_name] = data_qc_mito
            self.add_data_source(f, s_name)

        self.data_umap = dict()
        for f in self.find_log_files("checkatlas/umap"):
            # copy figures to multiqc data folder
            shutil.copy2(os.path.join(f["root"], f["fn"]), fig_dir)
            input_fname = f["s_name"].replace("_checkatlas_umap", "")
            s_name = self.clean_s_name(input_fname, f)
            self.data_umap[s_name] = f["fn"]
            self.add_data_source(f, s_name)

        self.data_tsne = dict()
        for f in self.find_log_files("checkatlas/tsne"):
            # copy figures to multiqc data folder
            shutil.copy2(os.path.join(f["root"], f["fn"]), fig_dir)
            input_fname = f["s_name"].replace("_checkatlas_tsne", "")
            s_name = self.clean_s_name(input_fname, f)
            self.data_tsne[s_name] = f["fn"]
            self.add_data_source(f, s_name)

        self.data_metric_cluster = dict()
        for f in self.find_log_files("checkatlas/cluster"):
            input_fname = f["s_name"].replace("_checkatlas_mcluster", "")
            s_name = self.clean_s_name(input_fname, f)
            data = parse_metric_logs(f["f"])
            for key, item in data.items():
                self.data_metric_cluster[key] = item
            self.add_data_source(f, s_name)

        self.data_metric_annot = dict()
        for f in self.find_log_files("checkatlas/annotation"):
            input_fname = f["s_name"].replace("_checkatlas_mannot", "")
            s_name = self.clean_s_name(input_fname, f)
            data = parse_metric_logs(f["f"])
            for key, item in data.items():
                self.data_metric_annot[key] = item
            self.add_data_source(f, s_name)

        self.data_metric_dimred = dict()
        for f in self.find_log_files("checkatlas/dimred"):
            input_fname = f["s_name"].replace("_checkatlas_mdimred", "")
            s_name = self.clean_s_name(input_fname, f)
            data = parse_metric_logs(f["f"])
            for key, item in data.items():
                self.data_metric_dimred[key] = item
            self.add_data_source(f, s_name)

        if len(self.data_summary) > 0:
            log.info("Found {} summary tables".format(len(self.data_summary)))
        if len(self.data_adata) > 0:
            log.info("Found {} adata tables".format(len(self.data_adata)))
        if len(self.data_qc_fig) > 0:
            log.info("Found {} QC violin plots".format(len(self.data_qc_counts)))
        if len(self.data_qc_counts) > 0:
            log.info("Found {} QC counts tables".format(len(self.data_qc_counts)))
        if len(self.data_qc_genes) > 0:
            log.info("Found {} QC genes tables".format(len(self.data_qc_genes)))
        if len(self.data_qc_mito) > 0:
            log.info("Found {} QC mito tables".format(len(self.data_qc_mito)))
        if len(self.data_umap) > 0:
            log.info("Found {} UMAP figures".format(len(self.data_umap)))
        if len(self.data_tsne) > 0:
            log.info("Found {} t-SNE figures".format(len(self.data_tsne)))
        if len(self.data_metric_cluster) > 0:
            log.info("Found {} metric cluster tables".format(len(self.data_metric_cluster)))

        self.write_data_file(self.data_summary, "multiqc_checkatlas-summary")
        self.write_data_file(self.data_adata, "multiqc_checkatlas_adata")
        self.write_data_file(self.data_metric_cluster, "multiqc_checkatlas_mcluster")
        self.write_data_file(self.data_metric_annot, "multiqc_checkatlas_mannot")
        self.write_data_file(self.data_metric_dimred, "multiqc_checkatlas_mdimred")
        # self.general_stats_addcols(self.checkatlas_data)

        self.add_sections()

    def add_sections(self):
        """
        Add the different sections for checkatlas report
        """
        self.add_summary_section()
        self.add_qc_fig_section()
        self.add_qc_section()
        self.add_umap_section()
        self.add_tsne_section()
        self.add_clustermetrics_section()
        self.add_annotationmetrics_section()
        self.add_dimredmetrics_section()
        self.add_specificitymetrics_section()
        self.add_adata_section()

    def add_summary_section(self):
        self.add_section(
            name="Atlas overview",
            anchor="checkatlas-summary",
            description="Overview of your single-cell atlases",
            helptext="""
                
                """,
            content=table.plot(self.data_summary),
        )

    def add_adata_section(self):
        config_adata = {"namespace": "adata_table"}
        headers = OrderedDict()
        headers["obs"] = {"scale": False}
        headers["obsm"] = {"scale": False}
        headers["var"] = {"scale": False}
        headers["varm"] = {"scale": False}
        headers["uns"] = {"scale": False}
        self.add_section(
            name="AnnData explorer",
            anchor="checkatlas-anndata",
            description="Exploration of your AnnData",
            helptext="""
                """,
            content=table.plot(self.data_adata, headers, pconfig=config_adata),
        )

    def add_qc_fig_section(self):
        type_viz = DICT_NAMING["checkatlas/qc_fig"]
        html_content = create_img_html_content(type_viz, self.data_qc_fig)
        self.add_section(
            name="QC visualisation",
            anchor="checkatlas-qc_fig",
            description="QC of your atlases.",
            helptext="""
    
                """,
            content=html_content,
        )

    def add_qc_section(self):
        type_viz = DICT_NAMING["checkatlas/qc"]
        config_qc = {
            # Building the plot
            "title": "QC total_counts",
            "ylab": "total_counts",  # X axis label
            "xlab": "log10(Cell Rank)",  # Y axis label
            "logswitch": True,
            "logswitch_active": True,
            "id": "qc_counts",  # HTML ID used for plot
            "categories": False,  # Set to True to use x values as categories instead of numbers.
        }
        self.add_section(
            name="QC total_counts",
            anchor="checkatlas-qc_counts",
            description="QC of your atlases log10(Cellrank vs total-counts.",
            helptext="""
            
                """,
            content=linegraph.plot(data=self.data_qc_counts, pconfig=config_qc),
        )

        config_qc = {
            # Building the plot
            "title": "QC n_genes_by_counts",
            "ylab": "n_genes_by_counts",  # X axis label
            "xlab": "log10(Cell Rank)",  # Y axis label
            "logswitch": True,
            "logswitch_active": True,
            "id": "qc_genes",  # HTML ID used for plot
            "categories": False,  # Set to True to use x values as categories instead of numbers.
        }
        self.add_section(
            name="QC n_genes_by_counts",
            anchor="checkatlas-qc_genes",
            description="QC of your atlases log10(Cellrank vs n_genes_by_counts.",
            helptext="""

                """,
            content=linegraph.plot(data=self.data_qc_genes, pconfig=config_qc),
        )

        config_qc = {
            # Building the plot
            "title": "QC pct_counts_mt",
            "ylab": "pct_counts_mt",  # X axis label
            "xlab": "log10(Cell Rank)",  # Y axis label
            "logswitch": True,
            "logswitch_active": True,
            "id": "qc_mito",  # HTML ID used for plot
            "categories": False,  # Set to True to use x values as categories instead of numbers.
        }
        self.add_section(
            name="QC pct_counts_mt",
            anchor="checkatlas-qc_mito",
            description="QC of your atlases log10(Cellrank vs pct_counts_mt.",
            helptext="""

                """,
            content=linegraph.plot(data=self.data_qc_mito, pconfig=config_qc),
        )

    def add_umap_section(self):
        type_viz = DICT_NAMING["checkatlas/umap"]
        html_content = create_img_html_content(type_viz, self.data_umap)
        self.add_section(
            name="UMAP visualisation",
            anchor="checkatlas-umap",
            description="UMAP of your atlases.",
            helptext="""
            
            """,
            content=html_content,
        )

    def add_tsne_section(self):
        type_viz = DICT_NAMING["checkatlas/tsne"]
        html_content = create_img_html_content(type_viz, self.data_tsne)
        self.add_section(
            name="t-SNE visualisation",
            anchor="checkatlas-tsne",
            description="t-SNE of your atlases.",
            helptext="""
                
                """,
            content=html_content,
        )

    def add_clustermetrics_section(self):
        config_cluster = {"namespace": "metric_cluster_table"}

        self.add_section(
            name="Classification metrics",
            anchor="checkatlas-clustmetrics",
            description="Quality control metrics calculated on your atlases.",
            helptext="""
            
            """,
            content=table.plot(data=self.data_metric_cluster, pconfig=config_cluster),
        )

    def add_annotationmetrics_section(self):
        self.add_section(
            name="Annotation metrics",
            anchor="checkatlas-annotmetrics",
            description="Quality control metrics calculated on your atlases.",
            helptext="""
            
            """,
            content=table.plot(self.data_metric_annot),
        )

    def add_dimredmetrics_section(self):
        self.add_section(
            name="Dimensionality reduction metrics",
            anchor="checkatlas-dimredmetrics",
            description="Quality control metrics calculated on your atlases.",
            helptext="""
                
                """,
            content=table.plot(self.data_metric_dimred),
        )

    def add_specificitymetrics_section(self):
        self.add_section(
            name="Specificity metrics",
            anchor="checkatlas-specmetrics",
            description="Quality control metrics calculated on your atlases.",
            helptext="""
            
            """,
            content="",
        )


def parse_qc_logs(f):
    """
    Parse logs from QC tables in .tsv files
    Order by CellRank
    Calc log10(CelllRank)
    :param f:
    :return:
    """
    data_qc_counts = dict()
    data_qc_genes = dict()
    data_qc_mito = dict()
    list_qc_counts = list()
    list_qc_genes = list()
    list_qc_mito = list()
    lines = f.splitlines()
    headers = lines[0].split("\t")
    try:
        index_counts = headers.index(QC_HEADER[0])
    except ValueError:
        index_counts = -1
    try:
        index_genes = headers.index(QC_HEADER[1])
    except ValueError:
        index_genes = -1
    try:
        index_mito = headers.index(QC_HEADER[2])
    except ValueError:
        index_mito = -1

    for i in range(1, len(lines)):
        line = lines[i].split("\t")
        if index_counts != -1:
            list_qc_counts.append(float(line[index_counts]))
        if index_genes != -1:
            list_qc_genes.append(float(line[index_genes]))
        if index_mito != -1:
            list_qc_mito.append(float(line[index_mito]))
    list_qc_counts.sort(reverse=True)
    list_qc_genes.sort(reverse=True)
    list_qc_mito.sort(reverse=True)

    for i in range(1, len(list_qc_counts)):
        data_qc_counts[math.log10(i)] = list_qc_counts[i]
    for i in range(1, len(list_qc_genes)):
        data_qc_genes[math.log10(i)] = list_qc_genes[i]
    for i in range(1, len(list_qc_mito)):
        data_qc_mito[math.log10(i)] = list_qc_mito[i]

    return data_qc_counts, data_qc_genes, data_qc_mito


def parse_firstline_table_logs(f):
    """
    Parse only header and first line of logs which are .tsv files
    Ex: _checkatlas.tsv, adata_checkatlas.tsv
    :param f:
    :return:
    """
    data = {}
    lines = f.splitlines()
    headers = lines[0].split("\t")
    for i in range(1, len(lines)):
        line = lines[i].split("\t")
        for j in range(0, len(line)):
            data[headers[j]] = line[j]
    return data


def parse_metric_logs(f):
    """
    Parse all lines of logs which are .tsv files
    Ex: _checkatlas.tsv, adata_checkatlas.tsv
    :param f:
    :return:
    """
    data = {}
    lines = f.splitlines()
    headers = lines[0].split("\t")
    for i in range(1, len(lines)):
        line = lines[i].split("\t")
        line_dict = {}
        for j in range(1, len(line)):
            line_dict[headers[j]] = line[j]
        data[line[0]] = line_dict
    return data


def create_img_html_content(type_viz, data):
    html_content = """
            <div class="tab">\n"""
    counter = 0
    tablinks = type_viz + "_tablinks"
    tabcontent = type_viz + "_tabcontent"
    for key, value in data.items():
        class_tab = tablinks
        if counter == 0:
            class_tab = tablinks + " active"
        html_content += add_selection_img_button(class_tab, type_viz, key, tablinks, tabcontent)
        counter += 1
    html_content += """</div>"""

    counter = 0
    for key, value in data.items():
        path_fig = os.path.join(config.data_dir_name, FIG_PATH, value)
        style = "display: none;"
        if counter == 0:
            style = "display: block;"
        html_content += add_div_img(path_fig, type_viz, key, style, tabcontent)
        counter += 1

    html_content += openpng_html_script
    return html_content


def add_selection_img_button(class_tab, type_viz, key, tablinks, tabcontent):
    return (
        """  <button class=\""""
        + class_tab
        + """\" onclick="openPNG(event, '"""
        + type_viz
        + "_"
        + key
        + """',
                            '"""
        + tablinks
        + "','"
        + tabcontent
        + """')">"""
        + key
        + """</button>\n"""
    )


def add_div_img(path_fig, type_viz, key, style, tabcontent):
    return (
        """<div id=\""""
        + type_viz
        + "_"
        + key
        + """\" class=\""""
        + tabcontent
        + """\" style =\""""
        + style
        + """\"><img src=\""""
        + path_fig
        + """\" >\n</div>\n"""
    )