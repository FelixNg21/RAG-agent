import ollama
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate


PROMPT_TEMPLATE = """
You are an assistant that ONLY provides information based on the given context. Follow these rules strictly:

### RULES:
1. ONLY use information present in the provided context
2. If the context doesn't contain the answer, respond with "Based on the provided context, I cannot answer this question."
3. NEVER make up or infer information not explicitly stated in the context
4. Do NOT use prior knowledge
5. Cite specific sections from the context using page numbers where available
6. Express uncertainty when the context is ambiguous
7. Be concise and direct in your responses

### CONTEXT:
{context}

### QUESTION:
{question}

### RESPONSE:
"""


def extract_model_names(json):
    return [model['model'] for model in json['models']]


class OllamaInterface:
    def __init__(self, model: str, db: Chroma):
        self.ollama = ollama
        self.ollama_model_str = model
        self.db = db
        # load LLM into memory
        self.ollama.generate(model=self.ollama_model_str,
                             keep_alive=-1)

    def query(self, prompt: str, use_context: bool = True, history: list = None, history_limit: int = 5, context=None):
        if context is None:
            context = []
        try:
            if use_context:
                context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in context])
                prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
                prompt_updated = prompt_template.format(context=context_text, question=prompt)
            else:
                prompt_updated = prompt
            if history:
                chat_history = history + [{"role": "user", "content": prompt_updated}]
            else:
                chat_history = [{"role": "user", "content": prompt_updated}]
            chat_history = chat_history[-(history_limit * 2):]
            return self.ollama.chat(
                model=self.ollama_model_str,
                messages=chat_history,
                stream=False,
                keep_alive=-1
            )
        except Exception as e:
            print(f"Error querying Ollama: {e}")
            return {"message": {"content": "An error occurred. Please try again."}}

    def get_context(self, prompt: str, doc_ids=None):
        filters = None
        if doc_ids:
            if isinstance(doc_ids, str):
                if "," in doc_ids:
                    doc_ids = ["./data/pdfs/"+id.strip() for id in doc_ids.split(",")]
                else:
                    doc_ids = ["./data/pdfs/" + doc_ids]

            if len(doc_ids) == 1:
                filters = {"source": doc_ids[0]}
            else:
                filters = {"source": {"$in": doc_ids}}
        print("Filters: ", filters)
        if filters is None:
            filtered_context = self.db.similarity_search_with_score(
                query=prompt,
                k=5
            )
        else:
            filtered_context = self.db.similarity_search_with_score(
                query=prompt,
                k=5,
                filter=filters
            )
            print("Filtered context: ", filtered_context)

        return filtered_context

    def get_details(self):
        details = self.ollama.list()
        return extract_model_names(details)

    def pull_model(self, model_name: str):
        try:
            self.ollama.pull(model_name)
        except:
            return "Model not found"

    def get_current_model(self):
        return extract_model_names(self.ollama.ps())

    def switch_model(self, model_name: str):
        self.ollama.generate(model=self.ollama_model_str,
                             keep_alive=0)
        self.ollama_model_str = model_name
        self.ollama.generate(model=self.ollama_model_str,
                             keep_alive=-1)
