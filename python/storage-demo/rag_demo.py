from sentence_transformers import SentenceTransformer
import numpy as np

documents = [
    "Managed identities allow Azure resources to authenticate without storing credentials.",
    "Azure Blob Storage stores unstructured object data such as files and images.",
    "Kubernetes uses pods as the smallest deployable workload unit.",
    "Docker images are immutable templates used to create containers.",
    "Azure RBAC determines what actions an identity may perform on Azure resources.",
]

query = "How can an Azure application authenticate without keeping a password?"

model = SentenceTransformer("all-MiniLM-L6-v2")

document_vectors = model.encode(documents, normalize_embeddings=True)
query_vector = model.encode(query, normalize_embeddings=True)

scores = document_vectors @ query_vector

ranking = np.argsort(scores)[::-1]

for index in ranking:
    print(f"{scores[index]:.3f} | {documents[index]}")
    
top_k = 2
retrieved = [documents[i] for i in ranking[:top_k]]

context = "\n".join(retrieved)

print("\nRetrieved context:")
print(context)

prompt = f"""
Answer the question using only the supplied context.
If the context does not contain the answer, say you don't know.

Context:
{context}

Question:
{query}
"""

print("\nRAG prompt:")
print(prompt)