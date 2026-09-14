# 数据下载操作说明

## A. Mauvieux 2025：优先下载，直接开放

数据页面：

<https://data.mendeley.com/datasets/3p52ydcyv3/1>

DOI：`10.17632/3p52ydcyv3.1`

许可：CC BY 4.0。

操作步骤：

1. 打开上面的数据页面。
2. 点击页面中的 **Download All**。
3. 如果浏览器要求确认条款，按照页面提示确认CC BY 4.0许可。
4. 解压下载内容。
5. 在本项目中新建目录`data/raw/mauvieux_2025/`。
6. 将解压后的文件原样放入该目录，不要改文件名。
7. 保留数据集自带的README和数据字典。
8. 不要把`data/raw/`提交到GitHub；本项目的`.gitignore`已经排除它。

公开页面说明该数据包含两个夜班工人研究：24人的横断面研究，以及16人
在12周运动计划前后的纵向研究。每次观测覆盖连续9天，其中包括5个
22:30至05:30的夜班，并提供活动记录、睡眠指标、口腔温度、血压、认知
和体力测试。收到压缩包后，下一步必须以包内README和实际文件列为准，
不能只根据网页摘要猜测列名。

建议引用：

> Mauvieux, B. (2025). Exercise, circadian rhythms & night work. Mendeley
> Data, V1. https://doi.org/10.17632/3p52ydcyv3.1

## B. Bourdillon：直接开放的真实RR间期数据

数据页面：

<https://zenodo.org/records/4326598>

DOI：`10.5281/zenodo.4326598`

操作步骤：

1. 在Zenodo文件列表中下载`RR.zip`。
2. 解压后保留`Baseline`、`Depriv`和`Recov`原始目录结构。
3. 将`RR`文件夹放入`data/raw/bourdillon_2020/`。
4. 不要修改原始文件名，也不要把`data/raw/`提交到GitHub。
5. 在项目根目录运行：

```bash
python -m shiftrecover.cli bourdillon \
  --data-dir "data/raw/bourdillon_2020/RR" \
  --output-dir "results/bourdillon"
```

读取器会兼容原数据中的`spearated`拼写、无下划线文件名和已经按
`sup`/`std`分开的记录。对于未标记体位的合并文件，程序按照论文规定的
3–3分钟或6–6分钟测试时长分段，并明确标记为推断值。第1阶段只保留并
标记RR间期，不删除异位搏动，也不进行插值或计算HRV。

建议引用：

> Bourdillon, N. (2020). Sleep deprivation deteriorates heart rate variability
> and photoplethysmography. Zenodo. https://doi.org/10.5281/zenodo.4326598

## C. TILES-2018：主分析数据，需要注册和DUA

项目介绍：

<https://tiles-data.isi.edu/dataset2018_details>

下载入口：

<https://tiles-data.isi.edu/download>

数据论文：

<https://doi.org/10.1038/s41597-020-00655-3>

操作步骤：

1. 打开下载入口并点击 **Sign In**。
2. 按网站要求创建账户或登录。
3. 下载并阅读TILES-2018 Data Usage Agreement。
4. 签署并提交DUA。DUA主要要求不得重新识别参与者，也不得向未签署者
   分享原始数据。
5. 等待研究团队验证；通过后会收到下载信息。
6. 选择 **TILES-2018 Main Record**。本项目不需要Audio Record。
7. 主记录压缩后约100GB，确认硬盘至少预留约200GB用于下载、解压和
   中间文件。
8. 原始文件放入`data/raw/tiles_2018/`，不要提交至GitHub或云端公共仓库。

优先需要的目录：

```text
metadata/days-at-work/
metadata/participant-info/
fitbit/daily-summary/
fitbit/sleep-metadata/
fitbit/sleep-data/       # 需要睡眠阶段时再用
fitbit/heart-rate/       # 需要分钟级分析时再用
fitbit/step-count/       # 需要分钟级活动节律时再用
```

第一轮开发不需要下载或处理音频。OMsignal主要在上班期间佩戴，适合研究
班中负荷，但不一定覆盖班后多个休息日，因此个体恢复主分析优先使用全天
佩戴的Fitbit。

## D. 为什么先做模拟数据？

Mendeley数据观察期短，TILES又需要DUA和较大存储空间。先运行模拟数据
有三个作用：

1. 在接触真实数据前固定分析定义，避免看到结果后修改规则；
2. 测试跨午夜时间、缺失、下一工作块和未恢复等边界情况；
3. 让GitHub访问者无需受限数据也能立即运行整个方法。

模拟数据不能用于得出真实人群结论，README和结果中必须明确标记。

## E. 数据到手后的检查清单

下载后先不要直接建模。依次核对：

- 实际文件名和数据字典；
- 参与者ID是否能跨表连接；
- 日期、当地时间和时区；
- 班次是排班记录、传感器推断还是自报；
- 夜班日期按开始日还是结束日标记；
- 每日设备佩戴时间；
- 主睡眠与小睡如何区分；
- 缺失值和设备伪影；
- 数据许可允许展示哪些派生结果。
