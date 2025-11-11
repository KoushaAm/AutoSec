from transformers import AutoTokenizer, AutoModelForCausalLM
import transformers
import torch
import models.config as config
from utils.mylogger import MyLogger
import os
from models.llm import LLM
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"
_model_name_map = {
    "starcoder" : "bigcode/starcoder",
    "starcoder2-15b": "bigcode/starcoder2-15b"
    
}

class StarCoderModel(LLM):
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        super().__init__(model_name, logger, _model_name_map, **kwargs)
        self.terminators = [
            self.pipe.tokenizer.eos_token_id,
            #        self.pipe.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]
    
    def predict(self, main_prompt, batch_size=0, no_progress_bar=False): 
        # assuming 0 is system and 1 is user
        #system_prompt = main_prompt[0]['content'
        def rename(d):            
            return d[0]['content'] + '\n'+ d[1]['content']
            #print(d)
            #print(newd)
            
            
        if batch_size > 0:
            prompts = [rename(p) for p in main_prompt]
            #print(prompts[0])
            self.model_hyperparams['temperature']=0.01
            return self.predict_main(prompts, batch_size=batch_size, no_progress_bar=no_progress_bar)
        else:
            prompt = self.pipe.tokenizer.apply_chat_template(
            main_prompt, 
            tokenize=False, 
            add_generation_prompt=True
            )
            self.model_hyperparams['temperature']=0.01
            #print(prompt)
            return self.predict_main(prompt, no_progress_bar=no_progress_bar)
