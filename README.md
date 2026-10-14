# CrossAS 中文使用说明

<p align="center"><strong>CrossAS · 跨物种等位基因特异性 SNP（AS-SNP）预测工具</strong></p>

CrossAS 是一款基于深度学习的**等位基因特异性 SNP（Allele-Specific SNP，AS-SNP）分类预测工具**。它使用 DNA 序列和经微调的深度学习模型，预测目标 SNP **属于 AS-SNP 的概率**。CrossAS 提供启动子（Promoter）和增强子（Enhancer）两类模型，支持人（Human）与猪（Pig）基因组，并支持使用一个物种训练的模型对另一物种参考基因组上的 SNP 进行跨物种预测。

## 1. 功能与模型

- **单个 SNP 预测**：输入染色体及 SNP 坐标，返回 AS-SNP 预测概率。
- **批量 SNP 预测**：读取 TSV/CSV 文件，一次预测多个位点，并保存结果。
- **启动子 / 增强子模型**：根据 SNP 所关联的顺式调控元件类型选用模型。
- **跨物种预测**：模型来源物种与输入参考基因组物种可以不同。
- **双操作模式**：支持命令行（CLI）及可视化网页界面。

| 模型名称 | 说明 |
| --- | --- |
| `human-promoter` | 人启动子 AS-SNP 预测模型 |
| `human-enhancer` | 人增强子 AS-SNP 预测模型 |
| `pig-promoter` | 猪启动子 AS-SNP 预测模型 |
| `pig-enhancer` | 猪增强子 AS-SNP 预测模型 |

## 2. 软件目录

```text
CrossAS/
├── crossas/                        # 软件核心代码、CLI、网页服务与模型结构
├── resources/
│   ├── fine_tuned_models/          # 四种微调模型的权重
│   └── genomes/                    # 人、猪参考基因组 FASTA
├── example/                        # 批量输入示例
├── results/                        # 预测结果（可按需创建）
├── crossas.ini                     # 模型与参考基因组路径配置
├── requirements.txt
├── pyproject.toml
└── README.md
```

`resources/` 由 Hugging Face 单独提供，安装源码后仍需下载这些资源，具体见第 4 节。

## 3. Conda 环境创建与安装

推荐使用 **Python 3.11**，在 CrossAS 项目根目录依次运行：

```bash
conda create -n CrossAS python=3.11 -y
conda activate CrossAS
cd ./CrossAS
pip install -r requirements.txt
pip install -e .
```

安装完成后检查：

```bash
crossas --version
crossas -h
crossas models
```

查看子命令帮助：

```bash
crossas predict -h
crossas batch -h
crossas serve -h
```

## 4. 下载模型权重和参考基因组（resources）

资源仓库：[Ancle666/CrossAS](https://huggingface.co/datasets/Ancle666/CrossAS/tree/main)

在 **CrossAS 项目根目录**运行以下命令，分别创建目标目录并下载所需资源。所有文件均保存到 `resources/` 对应位置，下载命令使用 `wget -c -O` 支持断点续传并指定本地文件名。

```bash
# human-promoter 模型权重
mkdir -p resources/fine_tuned_models/human_promoter
wget -c -O resources/fine_tuned_models/human_promoter/pytorch_model.bin \
'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/fine_tuned_models/human_promoter/pytorch_model.bin?download=true'

# human-enhancer 模型权重
mkdir -p resources/fine_tuned_models/human_enhancer
wget -c -O resources/fine_tuned_models/human_enhancer/pytorch_model.bin \
 'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/fine_tuned_models/human_enhancer/pytorch_model.bin?download=true'

# pig-promoter 模型权重
mkdir -p resources/fine_tuned_models/pig_promoter
wget -c -O resources/fine_tuned_models/pig_promoter/pytorch_model.bin \
  'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/fine_tuned_models/pig_promoter/pytorch_model.bin?download=true'

# pig-enhancer 模型权重
mkdir -p resources/fine_tuned_models/pig_enhancer
wget -c -O resources/fine_tuned_models/pig_enhancer/pytorch_model.bin \
  'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/fine_tuned_models/pig_enhancer/pytorch_model.bin?download=true'

# 人参考基因组（hg38）
mkdir -p resources/genomes
wget -c -O resources/genomes/hg38.fa.gz \
  'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/genomes/hg38.fa.gz?download=true'

# 猪参考基因组（Sscrofa11.1）
mkdir -p resources/genomes
wget -c -O resources/genomes/Sus_scrofa.Sscrofa11.1.dna.toplevel.fa.gz \ 'https://huggingface.co/datasets/Ancle666/CrossAS/resolve/main/resources/genomes/Sus_scrofa.Sscrofa11.1.dna.toplevel.fa.gz?download=true'
```

### 4.1 配置模型及基因组路径

下载完成后，检查项目根目录的 `crossas.ini`。示例配置：

```ini
[paths]
# All paths may be absolute or relative to this crossas.ini file.
resource_dir = ./resources
result_dir = ./result

[genomes]
human = ./resources/genomes/hg38.fa.gz
pig = ./resources/genomes/Sus_scrofa.Sscrofa11.1.dna.toplevel.fa.gz

[models]
human-promoter = ./resources/fine_tuned_models/human_promoter/pytorch_model.bin
human-enhancer = ./resources/fine_tuned_models/human_enhancer/pytorch_model.bin
pig-promoter = ./resources/fine_tuned_models/pig_promoter/pytorch_model.bin
pig-enhancer = ./resources/fine_tuned_models/pig_enhancer/pytorch_model.bin
```

以上路径为项目 README 中约定的本地布局；请确保与**实际下载文件**一致。路径可以为绝对路径，或相对于 `crossas.ini` 的相对路径。

执行资源检查：

```bash
crossas check
```

如需使用独立的配置文件，可设置环境变量：

```bash
export CROSSAS_CONFIG=/path/to/crossas.ini
```

## 5. 命令行使用

### 5.1 单个 SNP 预测

使用猪启动子模型，预测猪参考基因组 `chr1` 上的目标 SNP：

```bash
crossas predict -m pig-promoter -g pig chr2 130071886 130071887
```

将结果保存为 TSV：

```bash
crossas predict -m pig-promoter -g pig chr2 130071886 130071887 -o results/single_prediction.tsv
```

输出 JSON：

```bash
crossas predict -m pig-promoter -g pig chr2 130071886 --json
```

坐标采用 **0-based、左闭右开**区间 `[start, end)`。一个 SNP 长度为 1 bp，因此 `end = start + 1`；单 SNP 预测中可以不填写 `end`。

### 5.2 跨物种预测

使用**人启动子模型**，预测**猪参考基因组**中的目标 SNP：

```bash
crossas predict -m human-promoter -g pig chr2 130071886 130071887
```

`-m` 指定**模型**，`-g` 指定**待预测序列所属的参考基因组**。两者可以不同，但跨物种结果应结合数据分布差异谨慎解读。

### 5.3 批量 SNP 预测

准备制表符分隔的 TSV 文件，例如 `example/batch_variants.tsv`：

```tsv
id	chrom	start	end
snp_001	chr2	130071886	130071887
snp_002	chr1	2000000	2000001
```

运行：

```bash
crossas batch -m pig-promoter -g pig \
  -i example/batch_variants.tsv \
  -o results/pig_promoter_batch.tsv \
  -b 32
```

其中：

| 参数 | 作用 |
| --- | --- |
| `-m, --model` | 预测模型，如 `pig-promoter` |
| `-g, --genome` | 输入 SNP 所使用的参考基因组，如 `pig` |
| `-i, --input` | 批量输入 TSV/CSV 路径 |
| `-o, --output` | 预测结果输出路径 |
| `-b, --batch-size` | 批量推理大小，例如 `32` |
| `--device` | 推理设备：`auto`、`cpu` 或 `cuda`（如适用） |

如果输入表中包含 `genome` 列，也可以为每行提供对应参考基因组；当该列缺失时，可用 `-g` 指定统一的参考基因组。

## 6. 网页界面使用

启动网页服务（自动选择 CPU / CUDA）：

```bash
crossas serve --host 0.0.0.0 --port 5000 --device auto
```

如需强制使用 CPU：

```bash
crossas serve --host 0.0.0.0 --port 5000 --device cpu
```

在运行服务的计算机上，通过浏览器访问：

```text
http://127.0.0.1:5000/static/html/as_pred.html
```

网页界面提供：

- **Single Variant Prediction**：单个 SNP 的 AS-SNP 预测。
- **Batch Variant Prediction**：上传包含多个 SNP 的文件进行批量预测。
- **Prediction Model**：选择启动子或增强子模型。
- **Reference Genome**：选择输入 SNP 对应的参考基因组。
- **Result Preview / Download**：查看、导出批量 TSV 结果。

## 7. 输出结果解释

CrossAS 输出目标 SNP 的 AS-SNP 预测概率。常见输出字段包括：

| 字段 | 说明 |
| --- | --- |
| `as_prob` | 被模型预测为 AS-SNP 的概率（0～1） |
| `no_as_prob` | 被预测为非 AS-SNP 的概率 |
| `label` | 模型给出的预测类别 |
| `status` | 当前记录的预测状态 |
| `error` | 预测失败时的错误信息（如存在） |

批量输出通常还保留输入 SNP 的标识符、染色体与坐标等字段。输出概率不代表等位基因调控效应大小或效应方向，不应直接解释为实验检出的等位基因不平衡比例。

## 8. 常见问题

**Q：为什么运行时报找不到模型文件或参考基因组？**  
A：确认已下载 `resources/`、检查 `crossas.ini` 路径，然后运行 `crossas check`。

**Q：不同物种的模型和参考基因组是否可以混用？**  
A：支持将人或猪模型用于另一物种的参考基因组 SNP；但跨物种预测仍需考虑模型泛化能力与序列分布差异。

**Q：单个位点输入坐标需要注意什么？**  
A：使用 0-based、左闭右开区间，单个 SNP 应满足 `end = start + 1`。

---

**资源下载地址**：https://huggingface.co/datasets/Ancle666/CrossAS/tree/main  
**适用版本**：CrossAS V1.0
