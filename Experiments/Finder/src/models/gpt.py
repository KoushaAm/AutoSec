import os
from tqdm.contrib.concurrent import thread_map
from openai import OpenAI

import src.models.config as config
from src.utils.mylogger import MyLogger
from src.models.llm import LLM

_model_name_map = {
    "gpt-4": "gpt-4-0125-preview",
    "gpt-3.5": "gpt-3.5-turbo-0125",
    "gpt-4-1106": "gpt-4-1106-preview",
    "gpt-4-0613": "gpt-4-0613"
}
_OPENAI_DEFAULT_PARAMS = {"temperature": 0, "n": 1, "max_tokens": 4096, "stop": "", "seed": 345 }

class GPTModel(LLM):
    def __init__(self, model_name, logger: MyLogger, **kwargs):
        super().__init__(model_name, logger, _model_name_map, **kwargs)
        if ("openai_api_key" in kwargs) and (kwargs["openai_api_key"] is not None):
            api_key = kwargs["openai_api_key"]
        else:
            api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.logprobs = None
        for k in _OPENAI_DEFAULT_PARAMS:
            if k in kwargs:
                #print(f"Setting {k}:{kwargs[k]}")
                _OPENAI_DEFAULT_PARAMS[k] = kwargs[k]

    def predict(self, prompt, expect_json=False, batch_size=0, no_progress_bar=False):
        if batch_size == 0:
            return self._predict(prompt, expect_json)
        args = range(0, len(prompt))
        responses = thread_map(
            lambda x: self._predict(prompt[x], expect_json),
            args,
            max_workers=batch_size,
            disable=no_progress_bar)
        return responses

    def _predict(self, main_prompt, expect_json=False):
        # assuming 0 is system and 1 is user
        system_prompt = main_prompt[0]['content']
        user_prompt = main_prompt[1]['content']
        prompt = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        if 'logprobs' in self.kwargs:
            _OPENAI_DEFAULT_PARAMS['logprobs']=self.kwargs["logprobs"]
        if 'top_logprobs' in self.kwargs:
             _OPENAI_DEFAULT_PARAMS['top_logprobs']=self.kwargs["top_logprobs"]
        if expect_json:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=prompt,
                response_format={"type": "json_object"},
                **_OPENAI_DEFAULT_PARAMS)
        else:
            response = self.client.chat.completions.create(
                            model=self.model_id,
            messages=prompt,
            **_OPENAI_DEFAULT_PARAMS)
        if response.choices[0].logprobs != None:
            self.logprobs=response.choices[0].logprobs.content
        else:
            self.logprobs=None
        response=response.choices[0].message.content

        return response


if __name__ == '__main__':
    from src.prompts import SYSTEM_PROMPTS, USER_PROMPTS
    gpt=GPTModel('gpt-4', None)
    system_prompt=SYSTEM_PROMPTS['SINK']
    user_prompt=USER_PROMPTS["SINK"].format(cwe_description="Command Injection",
                                            cwe_id="78",
                                            functions="""
"java.lang","RuntimeException","RuntimeException"
"java.lang","Runtime","exec"
"java.lang","Runtime","getRuntime"
"java.lang","Runtime","exec"
"java.lang","Runtime","getRuntime"
"java.lang","Runtime","addShutdownHook"
"java.lang","Runtime","getRuntime"
"java.lang","Runtime","removeShutdownHook"
"java.lang","Runtime","getRuntime"
"java.lang","RuntimeException","RuntimeException"
"java.lang","Runtime","freeMemory"
"java.lang","Runtime","getRuntime"
"java.lang","Runtime","removeShutdownHook"
"java.lang","Runtime","getRuntime"
"java.lang","Runtime","addShutdownHook"
"java.lang","Runtime","getRuntime"
"java.lang","RuntimeException","RuntimeException"
"java.lang","RuntimeException","RuntimeException"
"java.lang","RuntimeException","RuntimeException"
"java.lang","RuntimeException","RuntimeException"
"java.lang","RuntimeException","RuntimeException"
"java.lang","RuntimeException","RuntimeException"
"""
                                            )

    gpt.predict([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
