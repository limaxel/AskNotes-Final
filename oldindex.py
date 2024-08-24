import os
import uuid

import mysql.connector
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.jinaai import JinaEmbedding

from flask import Flask, request, flash
from llama_index.llms.ollama import Ollama
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "./uploads"
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ALLOWED_EXTENSIONS = {'docx', 'pdf', 'pptx', 'txt'}

tidb_connection_url = os.getenv("TIDB_CONNECTION_URL")

tidb = mysql.connector.connect(
  host=os.getenv("TIDB_HOST"),
  user=os.getenv("TIDB_USER"),
  password=os.getenv("TIDB_PASS"),
)

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


embed_model = JinaEmbedding(
    api_key="jina_2c3c13e3c0724d37b7555aab416c094fUjq45ixP05P75Y4wlGqKb1lBg9pz",
    model="jina-embeddings-v2-base-en",
)

Settings.llm = Ollama(model="llama3", request_timeout=360.0)


@app.route("/upload", methods=['POST'])
def file_upload():
    if 'file' not in request.files:
        flash('No file part')
        return "No file part"
    files = request.files.getlist("file")
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    ufid = uuid.uuid4()  # unique folder id
    folder = f"{app.config['UPLOAD_FOLDER']}/{ufid}"
    os.makedirs(folder)
    for file in files:
        if file.filename == '':
            flash('No selected file')
            return "No selected file"
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(folder, filename))

    documents = SimpleDirectoryReader(folder).load_data()
    index = VectorStoreIndex.from_documents(
        documents=documents, embed_model=embed_model
    )

    tidb_cursor = tidb.cursor()
    sql = ("INSERT INTO courseMaterials (id, fileName, filePath, vector, courseId, userId) VALUES (%s, %s, %s, %s, %s, "
           "%s)")
    val = (uuid.uuid4(), "Highway 21")
    tidb_cursor.execute(sql, val)
    '''
    query_engine = index.as_query_engine()
    response = query_engine.query("what can you tell me about?")
    print(response)
    '''

    return "<p>Hello, World!</p>"

@app.route("/chat", methods=['GET'])
def chat():
    VectorStoreIndex.from_vector_store()

if __name__ == "__main__":
    app.run(port=8080, debug=True)
