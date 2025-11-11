from transformers import AutoTokenizer, AutoModelForCausalLM
import transformers
import torch
import models.config as config
from tqdm.contrib.concurrent import thread_map
from together import Together
from utils.mylogger import MyLogger
import os
from models.llm import LLM
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"

_model_name_map = {
    "llama-2-7b-chat": "meta-llama/Llama-2-7b-chat-hf",
    "llama-2-13b-chat": "meta-llama/Llama-2-13b-chat-hf",
    "llama-2-70b-chat": "meta-llama/Llama-2-70b-chat-hf",
    "llama-2-7b": "meta-llama/Llama-2-7b-hf",
    "llama-2-13b": "meta-llama/Llama-2-13b-hf",
    "llama-2-70b": "meta-llama/Llama-2-70b-hf",
    "llama-3-8b" : "meta-llama/Meta-Llama-3-8B-Instruct",
    "llama-3.1-8b" : "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "llama-3-70b" : "meta-llama/Meta-Llama-3-70B-Instruct",
    "llama-3.1-70b" : "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "llama-3-70b": "meta-llama/Meta-Llama-3-70B-Instruct",
    "llama-3-70b-tai": "meta-llama/Meta-Llama-3-70B-Instruct-Turbo"
}

class LlamaModel(LLM):
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        super().__init__(model_name, logger, _model_name_map, **kwargs)
        if "-tai" in self.model_name:
            self.together_client = Together()
        else:
            self.terminators = [
                self.pipe.tokenizer.eos_token_id,
                self.pipe.tokenizer.convert_tokens_to_ids("<|eot_id|>")
            ]

    def predict(self, main_prompt, batch_size=0, no_progress_bar=False):
        if "-tai" in self.model_name:
            return self.predict_with_together_ai(main_prompt, batch_size, no_progress_bar)
        else:
            return self.predict_local(main_prompt, batch_size, no_progress_bar)

    def predict_with_together_ai(self, main_prompt, batch_size, no_progress_bar):
        if batch_size == 0:
            return self.predict_one_with_together_ai(main_prompt)
        else:
            args = range(0, len(main_prompt))
            responses = thread_map(
                lambda x: self.predict_one_with_together_ai(main_prompt[x]),
                args,
                max_workers=batch_size,
                disable=no_progress_bar,
            )
            return responses


    def predict_one_with_together_ai(self, prompt):
        completion = self.together_client.chat.completions.create(
            model=_model_name_map[self.model_name],
            messages=prompt,
            # response_format={"type": "json_object"},
            temperature=0)
        response = completion.choices[0].message.content
        return response

    def predict_local(self, main_prompt, batch_size=0, no_progress_bar=False):
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
