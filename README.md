
# Consistency in Large Language Models for Reliable Patient Feedback Classification in Production

## Overview
This repository contains the code for implementing the Dual Consistency method with any LLM API for natural language classification. The provided implementation example classifies hospitalized patients' feedback among 21 categories and 2 tones, favorable and unfavorable, to identify areas for improvement in hospital quality of care. The code is designed to be used by `worker.py` to act as a worker in a production-scale application, handling a large volume of patient feedback.

### General Behavior

The methods send API requests to an available LLM to produce consistency metrics. The three methods available are: self-consistency assessment, logical consistency assessment, and dual consistency assessment. Self-consistency assessment (SCA) performs a straightforward cross-selection. Two LLM runs classify the text with general prompt engineering methods, and only categories identified twice are kept. Logical consistency assessment (LCA) applies the philosophy of logic argument assessment methods. It directs the LLM to produce two structured Chains of Thought (CoT) encompassing a premise (a citation from the feedback), an implication selected from a predefined, human-made list, and a conclusion (the identified category). A deterministic algorithm evaluates if the implication given by the LLM can be found attached to the adequate category in the provided list. At least one CoT must present a valid structure to be accepted. Dual consistency assessment applies both assessments.

### RabbitMQ Integration

The application uses RabbitMQ for message queuing to handle the large volume of patient feedback efficiently. RabbitMQ ensures that the feedback data is processed asynchronously and reliably by the worker instances.

## Installation

### Requirements

```bash
python > 3.12
poetry
```

### Install

```bash
poetry install
```

### Configuration

To configure this project, follow the steps below:

1. **Copy the `.env.sample` file:**

   - Make a copy of the file named `.env.sample` and rename it to `.env`.
   - Fill the necessary variables (examples can be found in the `.env.sample`)

- **API_ENDPOINT**: This is the URL of the LLM API model.
- **API_KEY**: The API key for accessing the LLM service.
- **MODEL_NAME**: The name of the model used (e.g., `llama3-70b`).
- **CATEGORIES_PATH**: The path to the file containing the classification categories.
- **OUTPUT_STRUCTURE_PATH**: The path to the file defining the structure of the LLM's output.
- **INITIAL_classification_PROMPT_PATH**: The path to the file containing the initial classification prompt.
- **FEW_SHOT_COT_classification_PROMPT_PATH**: The path to the file containing the few-shot CoT (Chain-of-Thought) classification prompt.

3. **Save the `.env` file**:  
After configuring all the necessary variables, save the `.env` file. Your project is now ready to use the correct environment configuration.

## Run

```bash
poetry run python3 worker.py --output-dir=<directory-name> --input-csv=<input-csv-path>
poetry run python3 worker.py --output-dir=output --input-csv=data/inputs.csv
```
The program's output will be in the specified output folder.

## License

This tool is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full license text.

<hr>
<p align="left">
  <img src="img/logo-ERIOS.png" alt="ERIOS" style="height:100px;"/>
    <img src="img/CHU-montpellier.png" alt="CHU Montpellier" style="height:100px;"/>
    <img src="img/um-2.png" alt="Université Montpellier" style="height:100px;"/>
</p>

