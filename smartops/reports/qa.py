# reports/qa.py
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from .ollama_wrapper import OllamaLLM

def build_retriever():
    # gather docs
    from .models import Report
    docs = []
    
    # Check if there are any reports
    if not Report.objects.exists():
        # Return empty retriever with some default text
        embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        texts = ["No reports available yet. Please upload some data first."]
        metadatas = [{"report_id": 0, "title": "Default"}]
        vect = FAISS.from_texts(texts, embed, metadatas=metadatas)
        return vect
        
    for r in Report.objects.all():
        text = r.summary + "\n\n" + "\n".join([f"{ins.key}: {ins.text}" for ins in r.insights.all()])
        docs.append((text, {"report_id": r.id, "title": r.title}))
    
    # build embeddings
    embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    texts = [t for t,_ in docs]
    metadatas = [m for _,m in docs]
    vect = FAISS.from_texts(texts, embed, metadatas=metadatas)
    return vect

def answer_query(query):
    vect = build_retriever()
    retriever = vect.as_retriever(search_type="mmr", search_kwargs={"k":3})
    llm = OllamaLLM(model="qwen:0.5b")
    chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
    return chain.run(query)