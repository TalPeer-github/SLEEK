import pandas as pd
import numpy as np
import sklearn
import spacy
import nltk
import re
import torch
import statsmodels as sm
import seaborn as sns
import matplotlib.pyplot as plt
import faiss
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pickle

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'


def embedding_model():
    model = SentenceTransformer(EMBEDDING_MODEL)
    return model


def embedd_dataset(dataset,
                   model: SentenceTransformer = SentenceTransformer('all-MiniLM-L6-v2'),
                   text_field: str = 'content',
                   rec_num: int = -1) -> np.ndarray:
    """
    Load a dataset and embedd the text field using a sentence-transformer model
    :param dataset: pandas.DataFrame object to load
    :param model: The model to use for embedding
    :param text_field: The field in the dataset that contains the text
    :param rec_num: The number of records to load and embedd
    :return: np.ndarray: A tuple containing the dataset and the embeddings
    """

    embeddings = model.encode(dataset[text_field][:rec_num])
    return embeddings


def build_faiss_flatl2_index(embeddings: np.ndarray, dim: tuple):
    """
    This function builds a Faiss flat L2 index.
    Args:
        embeddings: An array of shape (n_index, dim) containing the index vectors.
        dim: The dimensionality of the vectors.
    Returns:
        A Faiss flat L2 index.
    """
    index = faiss.IndexFlatL2(dim[1])
    index.add(embeddings)
    return index


def build_faiss_lsh_index(embeddings: np.ndarray, dim: int, nbits: int, ):
    """
    This function builds a Faiss LSH index.
    Args:
        embeddings: An array of shape (n_index, dim) containing the index vectors.
        dim: The dimensionality of the vectors.
        nbits: The number of bits to use in the hash.
    Returns:
        A Faiss LSH index.
    """
    index = faiss.IndexLSH(dim, nbits)
    index.add(embeddings)
    return index


def train_index(index, sentence_embeddings: np.ndarray):
    index.add(sentence_embeddings)


def encode_query(query: str, model):
    return model.encode(query)


def compute_recall_at_k(
        nn_gt: np.ndarray,
        ann: np.ndarray,
        k: int,
):
    """
    This function computes the recall@k.
    Args:
        nn_gt: The ground truth nearest neighbors.
        ann: The approximate nearest neighbors.
        k: The number of nearest neighbors to consider.
    Returns:
        The recall@k.
    """
    return round(sum([len(set(ann[i]) & set(nn_gt[i])) / k for i in range(len(ann))]) / len(ann), 3)


def load_df(dir_path: str, file_name: str, file_fmt: str):
    file_path = f"{dir_path}/{file_name}.{file_fmt}"
    return pd.read_csv(file_path)


def retrieve_top_passages(query, model, index, chunks, top_n=5):
    query_embedding = model.encode([query], convert_to_numpy=True)
    distances, indices = index.search(query_embedding, top_n)
    results = [(chunks[idx], distances[0][i]) for i, idx in enumerate(indices[0])]
    return results


def create_splits(texts, split_chunk_size, split_overlap):
    """
    :param texts: texts to create splits for
    :param split_chunk_size: The maximum size of a chunk, where size is determined by the length_function.
    :param split_overlap:Target overlap between chunks. Overlapping chunks helps to mitigate loss of information when context is divided between chunks.
    :return: chunked texts
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=split_chunk_size,
        chunk_overlap=split_overlap
    )

    texts_chunks = text_splitter.split_text(texts)

    print(f'Created {len(texts_chunks)} chunks from {len(texts)} documents (passages)')
    return texts_chunks


def create_book_chunks(book_df, split_chunk_size=1000, split_overlap=0.3):
    chunks = []
    for i, chapter_content in enumerate(book_df['processed_content']):
        chapter_idx = book_df['str_idx'].iloc[i]
        chapter_chunks = create_splits(chapter_content, split_chunk_size=split_chunk_size, split_overlap=split_overlap)
        for j, c_chunk in enumerate(chapter_chunks):
            chunks.append((chapter_idx, j, c_chunk))
    try:
        chunks_df = pd.DataFrame.from_records(chunks, columns=["str_idx", "chunk_id", "chunk"])
        chunks_df.to_csv('data/chunks.csv', index=False)
        return chunks_df
    except:
        print("chunks CSV file could not be created.")


def retrieve(model, index, chunks):
    queries = []
    retrieval_results = {query: [] for query in queries}
    for query in queries:
        retrieval_results[query] = retrieve_top_passages(query, model, index, chunks)


def save_embeddings(embeddings: np.ndarray, file_path="data/embeddings.pkl"):
    with open(file_path, "wb") as f:
        pickle.dump(embeddings, f)


def load_embeddings(file_path="data/embeddings.pkl"):
    with open(file_path, "rb") as f:
        loaded_embeddings = pickle.load(f)
    return loaded_embeddings


def main():
    book_df = load_df(dir_path="data", file_name="book_df", file_fmt="csv")
    passages_df = load_df(dir_path="data", file_name="passages_df", file_fmt="csv")

    chunks_df = create_book_chunks(book_df, split_chunk_size=1000, split_overlap=0.3)
    model = embedding_model()

    embeddings = embedd_dataset(
        dataset=chunks_df,
        rec_num=-1,
        model=model,
        text_field='chunk',
    )
    save_embeddings(embeddings)
    embeddings_shape = embeddings.shape
    index = build_faiss_flatl2_index(embeddings, embeddings_shape)
    # queries = []
    # retrieval_results = {query: [] for query in queries}
    # for query in queries:
    #     retrieval_results[query] = retrieve_top_passages(query, model, index, chunks)


if __name__ == "__main__":
    main()
