# LIT-PCBA 与 PubChem BioAssay 的初步对照观察

在完成前期调研并联系导师后，我尝试进一步“看数据本身”。

目前选取了 **LIT-PCBA 的 MAPK1 子集**，并同时查看其对应的 **PubChem BioAssay AID 995**，希望通过二者对照，试着理解一个较接近机器学习训练格式的数据集，与其上游实验记录之间，到底发生了哪些信息压缩。

---

## 1. 初步记录

| SID | Compound / SMILES | LIT-PCBA Label | PubChem Outcome | Target / Assay | Measurement Type | Value / Relation | Negative Type | Context Preserved? | Evidence / Link | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 440151760 | CID 129284334 | N/A | Inactive | KDR / Kinase panel | Inhibition | = 17% | measured inactive | Partial | PubChem AID 1785989 | 明确经过实验测定并被标记为 inactive；仍需进一步确认该 assay 的具体判定阈值 |
| 440230063 | CID 24959105 | N/A | Inactive | EGFR / Millipore kinase activity assay | Inhibition | = -24% | measured inactive + validity flag | Partial | PubChem AID 1788980 | 同样被标记为 inactive，但同时存在 `Outside typical range` 的 validity flag，说明该结果的证据质量与普通 inactive 并不完全等价 |
|  |  |  |  |  |  |  |  |  |  |  |

---

## 2. 一个直接观察：同样的 `negative = 0`，实验语义可能不同

以第二条记录为例，如果最终为了机器学习训练，将其压缩为：

```text
compound -> 0
```

那么至少有以下信息没有进入最终标签：

```text
Inhibition = -24%
Data validity = Outside typical range
Assay = EGFR kinase activity assay
```

因此，虽然两个样本在最终二分类任务中都可能被表示为：

```text
negative = 0
```

但二者的实验背景、测量结果、数据质量、证据可信度并不完全相同。

这说明一个简单的二元标签可能会把不同科学含义的数据压缩到同一个训练目标中。

## 3. LIT-PCBA 与上游实验记录的差异

LIT-PCBA 的 MAPK1 数据中，官方将 308 个 active、61,567 个 inactive 整理为较直接的 active.smi、inactive.smi。

文件中只保留 SMILES + PubChem SID，接近机器学习训练所需的数据表示。而对应的 PubChem BioAssay AID 995 中，上游实验记录会区分更多状态，例如 full titration curve、partial curve、single-point activity、inactive、inconclusive，同时还可能保留具体测量值、activity score、assay 信息和数据质量状态。

因此可以粗略理解为一个信息压缩过程：

```text
真实 assay
    ↓
实验条件 + 测量值 + 判定结果 + 数据质量信息
    ↓
数据库结构化记录
    ↓
benchmark 清洗与任务化
    ↓
SMILES + 0/1
```

## 4. 需要避免的简单判断

把复杂 assay 记录压缩成 `SMILES + 0/1` 并不一定是不合理的。对于明确的二分类任务，这种表示具有明显优势：标签统一、数据结构简单、更容易进行模型训练与比较、避免模型直接依赖过多异质实验字段。

因此，真正值得研究的问题并不是信息被压缩了所以这种数据表示不好，而应该是：

> 在被压掉的信息中，是否存在对模型训练具有额外价值的部分？

更进一步，需要考察是否改善预测性能、是否改善分布外泛化、是否改善模型校准、是否有助于不确定性判断、是否能减少不同实验语义被错误合并的问题。

## 5. 可以考虑的三种数据表示层级

### Level 1：最简二分类标签

```text
molecule -> 0/1
```

适合标准 active / inactive 分类任务。

优点是简单、统一、易于训练。

缺点是大量实验上下文被压缩。

### Level 2：带阴性类型的标签

例如：

```text
molecule -> measured_inactive
molecule -> censored_negative
molecule -> qualitative_negative
molecule -> relative_negative
```

相比简单的 0/1，这种表示保留了“为什么它是阴性”的部分信息。

可能适合多任务学习、分层标签、ranking、weak supervision。

### Level 3：带实验上下文与证据的数据表示

例如保留：

```text
molecule
target
assay
measurement
value
relation
activity_outcome
validity
evidence
```

这种表示的信息最完整，但训练和建模也最复杂。

## 6. 目前更值得追问的问题

真正需要验证的是：

> 从 Level 1 提升到 Level 2 或 Level 3，是否存在稳定、可复现的额外收益？

而且这种收益可能具有明显的任务依赖性。

例如，一个可能的现象是：0/1 标签对于普通随机切分二分类任务可能已经足够、assay context 对新 assay 或分布外任务可能更重要、validity / confidence 对模型 calibration 可能具有价值、IC50 > x 或相对活性关系对排序任务可能比直接二值化更合适。

因此，这里更像是一个：

> 不同数据表示方式与不同学习任务之间的匹配问题。

## 7. 数据层面

从真实 assay 到 benchmark 的过程中，具体丢失了哪些信息、哪些信息是有意简化而哪些属于可能影响训练的语义损失、不同类型的 negative 是否被统一压缩成了同一个标签？

### 模型层面

被压缩的信息是否具有独立训练价值、这种价值是否只存在于特定任务、加入 context 后的收益能否排除只是增加特征数量或数据量造成的影响？

### 泛化层面

哪些信息对 random split 没有明显帮助但对 scaffold split、temporal split 或 unseen assay 更重要、validity、confidence、relation 等字段是否能改善模型校准或不确定性判断？

不能简单得出保存的信息越多，模型一定越好。

更合理的问题是：对于不同任务，应当保留到什么程度的信息，才能在数据复杂度和模型收益之间取得合适的平衡？
