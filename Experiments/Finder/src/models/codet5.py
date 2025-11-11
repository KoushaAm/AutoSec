from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM
import transformers
import torch
import models.config as config
from utils.mylogger import MyLogger
import os
from models.llm import LLM
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"

_model_name_map = {
    "codet5p-16b-instruct": "Salesforce/instructcodet5p-16b",
    "codet5p-16b": "Salesforce/codet5p-16b",
    "codet5p-6b": "Salesforce/codet5p-6b",
    "codet5p-2b": "Salesforce/codet5p-2b"
}

class CodeT5PlusModel():
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        #super().__init__(model_name, logger, _model_name_map, **kwargs)
        self.model_name=model_name
        self.tokenizer = AutoTokenizer.from_pretrained(_model_name_map[model_name])
        #dmap={'encoder': 0, 'decoder.transformer.wte': 0, 'decoder.transformer.drop': 0, 'decoder.transformer.h.0': 0, 'decoder.transformer.h.1': 1, 'decoder.transformer.h.2': 1, 'decoder.transformer.h.3': 1, 'decoder.transformer.h.4': 1, 'decoder.transformer.h.5': 2, 'decoder.transformer.h.6': 2, 'decoder.transformer.h.7': 2, 'decoder.transformer.h.8': 2, 'decoder.transformer.h.9': 3, 'decoder.transformer.h.10': 3, 'decoder.transformer.h.11': 3, 'decoder.transformer.h.12': 3, 'decoder.transformer.h.13': 4, 'decoder.transformer.h.14': 4, 'decoder.transformer.h.15': 4, 'decoder.transformer.h.16': 4, 'decoder.transformer.h.17': 5, 'decoder.transformer.h.18': 5, 'decoder.transformer.h.19': 5, 'decoder.transformer.h.20': 5, 'decoder.transformer.h.21': 6, 'decoder.transformer.h.22': 6, 'decoder.transformer.h.23': 6, 'decoder.transformer.h.24': 6, 'decoder.transformer.h.25': 4, 'decoder.transformer.h.26': 5, 'decoder.transformer.h.27': 6, 'decoder.transformer.h.28': 1, 'decoder.transformer.h.29': 1, 'decoder.transformer.h.30': 1, 'decoder.transformer.h.31': 2, 'decoder.transformer.h.32': 2, 'decoder.transformer.h.33': 2, 'decoder.transformer.ln_f': 3, 'decoder.lm_head': 3, 'enc_to_dec_proj': 3}
        self.model = AutoModelForSeq2SeqLM.from_pretrained(_model_name_map[model_name],
                                                      torch_dtype=torch.float16,
                                                      low_cpu_mem_usage=True,
                                                      trust_remote_code=True,
                                                      device_map="auto"
        )
        #print(self.model.hf_device_map)
        
        #self.model.to_bettertransformer()
   
    def predict(self, main_prompt): 
        # assuming 0 is system and 1 is user
        system_prompt = main_prompt[0]['content']
        user_prompt = main_prompt[1]['content']
        if 'instruct' in self.model_name:
            prompt = f"Instruction: {system_prompt}\\n Input:\\n {user_prompt} \\n Output:\\n"
        else:
            prompt = f"Input:\\n {user_prompt} \\n Output:\\n"
        #prompt = f"{user_prompt}"
        #inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        #return self.predict_main(prompt)
        encoding = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        if len(encoding) > 1000:
            return prompt, "Skipping, too long " + str(len(encoding))
        #encoding=encoding.to('cuda:3')
        encoding['decoder_input_ids'] = encoding['input_ids'].clone()
        outputs = self.model.generate(**encoding, max_length=2000)
        return prompt, self.tokenizer.decode(outputs[0], skip_special_tokens=True)
