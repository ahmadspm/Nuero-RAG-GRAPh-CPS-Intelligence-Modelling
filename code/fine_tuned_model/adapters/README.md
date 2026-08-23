# Adapters

Trained LoRA adapter checkpoints go here (this directory is where
`llm_fine_tune.py`'s `OUTPUT_DIR` should point, and what `inference.py` /
`merge_adapter.py` load from).

Checkpoints aren't committed to the repo — download the pretrained
adapter from [model_link](https://drive.google.com/file/d/1b_6akH2ZQDOi6QzALJX4YFFYvqS5-FTB/view?usp=sharing)
(same link as the root README) and unpack it here, or produce a new one
by running `../llm_fine_tune.py`.
