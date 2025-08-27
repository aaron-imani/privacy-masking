from collections import defaultdict
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer
)
from peft import LoraConfig, get_peft_model, AutoPeftModelForCausalLM, PeftModel
from trl import SFTTrainer, SFTConfig
import torch
import matplotlib.pyplot as plt
import os
import re
torch.backends.cuda.matmul.allow_tf32 = True
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Check if GPU benefits from bfloat16
if torch.cuda.get_device_capability()[0] >= 8:
    torch_dtype = torch.bfloat16
else:
    torch_dtype = torch.float16

# Read more: https://medium.com/data-science-in-your-pocket/a-practical-guide-to-fine-tuning-googles-gemma-3-270m-with-lora-ca03decf2ac1
# Another example: https://github.com/PromptEngineer48/Gemma3-270m-finetune/blob/main/share_finetune.ipynb
# https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora

pii_pattern = re.compile(r'\[.*?\]')
user_prompt = """Output all Personal Identifiable Information (PII) in the following text as a list of JSON objects with 'entity' and 'category' fields:
'{original_text}'
"""


def format_prompt_instruct(sample):
    # count_dict = defaultdict(int)
    # target_text = sample['target_text']
    # for match in pii_pattern.finditer(target_text):
    #     pii_type = match.group(0).strip('[]').upper()
    #     count_dict[pii_type] += 1
    #     target_text = target_text.replace(match.group(0), f"{pii_type}_{count_dict[pii_type]}", 1)
    
    messages = [
        {
            "role": "user",
            "content": user_prompt.format(original_text=sample['source_text']),
        },
        {"role": "assistant", "content": str(sample['entities'])},
    ]
    return {
        "messages": messages
    }


def format_prompt_base(sample):
    chat = f"""Replace any Personal Identifiable Information (PII) in the following text with <PIIType_occurence> format, e.g., EMAIL_1, PHONE_1:
'{sample['source_text']}'

Masked Text:
'{sample['target_text']}'
"""
    return chat


model_name = "google/gemma-3-270m-it"
ft_name = f"./{model_name.split('/')[-1]}-ft"
# Load the base model and tokenizer

# For base model replace with AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    device_map="auto",
    use_cache=False,
    attn_implementation="eager",
    torch_dtype=torch_dtype
)

# For instruct fine-tuned models
tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-270m-it")

# Potentially useful dataset for call centre data: https://huggingface.co/datasets/automated-analytics/piiceetah-call-centre
# More datasets:
# https://huggingface.co/datasets/automated-analytics/ai4privacy-pii-coarse-grained


dataset_name = "automated-analytics/gretel-pii-fine-grained" # https://huggingface.co/datasets/automated-analytics/gretel-pii-fine-grained/viewer/default/train?views%5B%5D=train&row=5
dataset = load_dataset(dataset_name, split="train")
dataset = dataset.map(format_prompt_instruct, remove_columns=dataset.features,batched=False)
# dataset = dataset.train_test_split(test_size=0.2, seed=42)
# print(model)

# print(tokenizer.apply_chat_template(dataset[10]['messages'],tokenize=False, add_generation_prompt=False))
# print(dataset[10]['messages'][1]['content'])
# exit()

# Configure PEFT (LoRA)
peft_config = LoraConfig(
    lora_alpha=16,
    lora_dropout=0.05,
    r=16,
    target_modules='all-linear',
    bias="none",
    task_type="CAUSAL_LM",
)

os.makedirs(f'./models/{ft_name}', exist_ok=True)


training_args = SFTConfig(
    output_dir=f'./models/{ft_name}',        # directory to save and repository id
    num_train_epochs=1,                     # number of training epochs
    per_device_train_batch_size=4,          # batch size per device during training
    gradient_accumulation_steps=4,          # number of steps before performing a backward/update pass
    gradient_checkpointing=True,            # use gradient checkpointing to save memory
    optim="adamw_torch_fused",              # use fused adamw optimizer
    logging_steps=25,                       # log every 25 steps
    save_strategy="epoch",                  # save checkpoint every epoch
    learning_rate=2e-4,                     # learning rate, based on QLoRA paper
    fp16=True if torch_dtype == torch.float16 else False,   # use float16 precision
    bf16=True if torch_dtype == torch.bfloat16 else False,   # use bfloat16 precision
    max_grad_norm=0.3,                      # max gradient norm based on QLoRA paper
    warmup_ratio=0.03,                      # warmup ratio based on QLoRA paper
    lr_scheduler_type="constant",           # use constant learning rate scheduler
    dataset_kwargs={
        "add_special_tokens": False, # We template with special tokens
        # "append_concat_token": True, # Add EOS token as separator token between examples
    }
)

# Initialize the SFTTrainer and Start Training
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    args=training_args,
    processing_class=tokenizer
)

# Start the training
trainer.train()
trainer.save_model(f'./models/{ft_name}/final')
