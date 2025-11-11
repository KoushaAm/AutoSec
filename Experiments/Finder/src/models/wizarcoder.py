from transformers import AutoTokenizer, AutoModelForCausalLM
import transformers
import torch
import models.config as config
from utils.mylogger import MyLogger
import os
from models.llm import LLM

#os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"
_model_name_map = {
    "wizardcoder-15b": "WizardLM/WizardCoder-15B-V1.0",
    "wizardcoder-34b-python": "WizardLM/WizardCoder-Python-34B-V1.0",
    "wizardcoder-13b-python": "WizardLM/WizardCoder-Python-13B-V1.0",
    "wizardlm-70b": "WizardLM/WizardLM-70B-V1.0",
    "wizardlm-13b": "WizardLM/WizardLM-13B-V1.2",    
    "wizardlm-30b": "WizardLM/WizardLM-30B-V1.0"
}
class WizardCoderModel(LLM):
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        super().__init__(model_name, logger, _model_name_map, **kwargs)
    
    def predict(self, main_prompt): 
        # assuming 0 is system and 1 is user
        system_prompt = main_prompt[0]['content']
        user_prompt = main_prompt[1]['content']
        prompt = user_prompt
        prompt = f"Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{system_prompt} \n\n {user_prompt}\n\n### Response:"
      
        return self.predict_main(prompt)
