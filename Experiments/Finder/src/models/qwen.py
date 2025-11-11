from transformers import AutoTokenizer, AutoModelForCausalLM
import transformers
import torch
import models.config as config
from utils.mylogger import MyLogger
import os
from models.llm import LLM
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"
_model_name_map = {
    "qwen2.5-coder-7b": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "qwen2.5-coder-1.5b": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
    "qwen2.5-32b": "Qwen/Qwen2.5-32B-Instruct",
    "qwen2.5-72b" : "Qwen/Qwen2.5-72B-Instruct"
    
}

class QwenModel(LLM):
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        super().__init__(model_name, logger, _model_name_map, **kwargs)
        self.terminators = [
                self.pipe.tokenizer.eos_token_id
        #        self.pipe.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

    def predict(self, main_prompt, batch_size=0, no_progress_bar=False): 
        # assuming 0 is system and 1 is user
       
        #prompt = f"<s>[INST] <<SYS>>\\n{system_prompt}\\n<</SYS>>\\n\\n{user_prompt}[/INST]"
        if batch_size > 0:
            prompts = [self.pipe.tokenizer.apply_chat_template(p, tokenize=False, add_generation_prompt=True) for p in main_prompt]
            self.model_hyperparams['temperature']=0.01
            return self.predict_main(prompts, batch_size=batch_size, no_progress_bar=no_progress_bar)
        else:
            prompt = self.pipe.tokenizer.apply_chat_template(
            main_prompt, 
            tokenize=False, 
            add_generation_prompt=True
            )

            #prompt = f"{user_prompt}"
            #inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
            self.model_hyperparams['temperature']=0.01
            return self.predict_main(prompt, no_progress_bar=no_progress_bar)

