import torch
torch.set_float32_matmul_precision('high')
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from transformers import pipeline

model_name = "google/gemma-3-270m-it"
tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-270m-it")
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)
# model = base_model

adapter_model_name="./models/gemma-3-270m-it-ft/final"
model = PeftModel.from_pretrained(base_model, adapter_model_name)
model.eval()

user_prompt = """Output all Personal Identifiable Information (PII) in the following text as a list of JSON objects with 'entity' and 'category' fields:
'{original_text}'
"""

# Load the model and tokenizer into the pipeline
pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)

def extract_pii(text, max_tokens=None):
    max_tokens = max_tokens or len(tokenizer(text).input_ids)
    messages = [
        {
            "role": "user",
            "content": user_prompt.format(original_text=text),
        },
    ]
    output = pipe(messages, max_new_tokens=max_tokens, return_full_text=False, temperature=0.1)[0]
    return output["generated_text"]

if __name__ == '__main__':
    original_text = "My name is Mahmoud Moshirpour and my email is john.doe@example.com. I live in 3244 Main St., Mission Viejo. His SSN is 542873775."
    text2 = 'Tenant: Alex Ramirez | Signer: San Diego Investors Co.'

    extracted_pii = extract_pii(text2, max_tokens=256)
    print(extracted_pii)
