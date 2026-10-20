# EnzChemRED NLP Pipeline

[This repository](https://ftp.ncbi.nlm.nih.gov/pub/lu/EnzChemRED/EnzChemRED_pipeline.tar) contains an end-to-end NLP pipeline for enzyme function extraction that uses the EnzChemRED dataset to fine-tune NLP methods. The pipeline consists of four main steps:

1. Literature triage
2. Named entity recognition (NER)
3. Named entity normalization (NEN)
4. Relation extraction (RE)

## 1. Literature Triage

Retrieves papers relevant to enzyme functions using LitSuggest.
Located in the `literature_triage` folder.

## 2. Named Entity Recognition (NER)

Tags chemical and protein mentions in the text using AIONER after fine-tuning using EnzChemRED.
Located in the `aioner` folder.

## 3. Named Entity Normalization (NEN)

Links chemical and protein mentions to stable unique database identifiers using MTCR and UniProt matching.

- Chemical linking to ChEBI: Located in the `mtcr` folder
- Protein linking to UniProt: Located in the `uniprot_norm` folder

## 4. Relation Extraction (RE)

Extracts information about enzymes and the chemical conversions they catalyze using a BioREx model fine-tuned for this purpose using EnzChemRED.
Located in the `biorex` folder.

## Citing EnzChemRED

If you use EnzChemRED in your research, please cite:

* Lai, PT., Coudert, E., Aimo, L. _et al._ EnzChemRED, a rich enzyme chemistry relation extraction dataset. _Sci Data_ **11**, 982 (2024). https://doi.org/10.1038/s41597-024-03835-7
```
@article{lai2024enzchemred,
  title         = {EnzChemRED, a rich enzyme chemistry relation extraction dataset}, 
  author        = {Po-Ting Lai and Elisabeth Coudert and Lucila Aimo and Kristian Axelsen and Lionel Breuza and Edouard de Castro and Marc Feuermann and Anne Morgat and Lucille Pourcel and Ivo Pedruzzi and Sylvain Poux and Nicole Redaschi and Catherine Rivoire and Anastasia Sveshnikova and Chih-Hsuan Wei and Robert Leaman and Ling Luo and Zhiyong Lu and Alan Bridge},
  journal       = {Scientific Data},
  volume        = {11},
  number        = {1},
  pages         = {982},
  year          = {2024},
  publisher     = {Nature Publishing Group UK London},
  doi           = {10.1038/s41597-024-03835-7}
}
```
