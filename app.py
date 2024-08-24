from dotenv import load_dotenv
import json
import shutil
import urllib.request
import uuid
import datetime

import mysql.connector
from flask import Flask, render_template, redirect, request, g
import os

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex, Settings, SummaryIndex
from llama_index.embeddings.openai import OpenAIEmbedding
#from llama_index.embeddings.jinaai import JinaEmbedding
#from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.tidbvector import TiDBVectorStore
from llama_index.llms.openai import OpenAI
from supabase import create_client, Client, ClientOptions
from werkzeug.local import LocalProxy

from flask_storage import FlaskSessionStorage
from notion_api import NotionAPI

'''Settings.llm = Ollama(model="llama3", request_timeout=360.0)
embed_model = JinaEmbedding(
            api_key="",
            model="jina-embeddings-v2-base-en",
            embed_batch_size=16,
        )'''

load_dotenv()

Settings.llm = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=360.0)
embed_model = OpenAIEmbedding(
            api_key=os.environ.get("OPENAI_API_KEY"),
            model="text-embedding-3-small",
            embed_batch_size=16,
        )

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")


def get_supabase() -> Client:
    if "supabase" not in g:
        g.supabase = Client(
            url,
            key,
            options=ClientOptions(
                storage=FlaskSessionStorage(),
                flow_type="pkce"
            ),
        )
    return g.supabase


supabase: Client = LocalProxy(get_supabase)

tidb = mysql.connector.connect(
    host=os.getenv("TIDB_HOST"),
    user=os.getenv("TIDB_USER"),
    password=os.getenv("TIDB_PASS")
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")


@app.route("/", methods=['GET'])
def index():
    return render_template('index.html')


@app.route("/signin", methods=['GET'])
def signin():
    response = supabase.auth.sign_in_with_oauth({
        "provider": "notion",
        "options": {
            "redirect_to": "https://asknotes.axellim.com:5000/signin/callback"
        }
    })
    return redirect(response.url)


@app.route("/signin/callback", methods=['GET'])
def signin_callback():
    code = request.args.get("code")
    next_path = request.args.get("next", "/initialise")

    if code:
        supabase.auth.exchange_code_for_session({"auth_code": code})

    return redirect(next_path)


@app.route("/dashboard", methods=['GET'])
def dashboard():
    supabase_session = supabase.auth.get_session()
    if supabase_session:
        notion_user_id = supabase_session.user.user_metadata.get("sub")
        tidb.reconnect()
        tidb_cursor = tidb.cursor()
        sql = "SELECT parent_id FROM asknotes.users WHERE id = %s"
        val = (notion_user_id,)
        tidb_cursor.execute(sql, val)
        user_result = tidb_cursor.fetchone()
        if user_result:
            parent_id = user_result[0]
            return render_template('dashboard.html', parent_id=parent_id.replace("-", ""))
        else:
            redirect("/")
    else:
        return "Unauthorized. Please <a href='/'>Sign In</a>"


@app.route("/initialise", methods=['GET'])
def initialise():
    global courses_last_updated
    parent_id, courses_id, chat_id, study_aids_id = None, None, None, None
    supabase_session = supabase.auth.get_session()
    if supabase_session:
        notion_user_id = supabase_session.user.user_metadata.get("sub")
        tidb.reconnect()
        tidb_cursor = tidb.cursor()
        sql = "SELECT * FROM asknotes.users WHERE id = %s"
        val = (notion_user_id,)
        tidb_cursor.execute(sql, val)
        user_result = tidb_cursor.fetchone()
        if user_result:
            return redirect("/dashboard")
        provider_token = supabase_session.provider_token
        notion_api = NotionAPI(provider_token)
        search_response = notion_api.search()
        if search_response["results"]:
            parent_id = search_response["results"][0]["id"]
            get_block_children_response = notion_api.get_block_children(parent_id)
            block_children_list = get_block_children_response["results"]
            if block_children_list:
                for children in block_children_list:
                    item_type = children["type"]
                    if item_type == "child_database":
                        item_child_database_title = children["child_database"]["title"]
                        if item_child_database_title == "Courses":
                            courses_id = children["id"]
                            courses_last_updated = children["last_edited_time"]
                    if item_type == "child_page":
                        item_child_page_title = children["child_page"]["title"]
                        if item_child_page_title == "Chat":
                            chat_id = children["id"]
                        if item_child_page_title == "Study Aids":
                            study_aids_id = children["id"]
        sql = (
            "INSERT INTO asknotes.users (id, notion_secret_key, parent_id, courses_id, chat_id, study_aids_id, courses_last_updated) VALUES (%s, %s, %s, %s, %s, %s, %s)")
        val = (notion_user_id, provider_token, parent_id, courses_id, chat_id, study_aids_id, courses_last_updated)
        tidb_cursor.execute(sql, val)
        tidb.commit()
        tidb_cursor.close()
        if parent_id is None or courses_id is None or chat_id is None or study_aids_id is None:
            return render_template('dashboard.html', title="Error initialising instance", status="template_error")
        else:
            return render_template('dashboard.html')
    else:
        return "Unauthorized. Please <a href='/'>Sign In</a>"


@app.route("/embedding", methods=["GET"])
def embedding():
    authorization = request.headers.get("Authorization")
    internal_api_secret_key = authorization[7:]
    if internal_api_secret_key == os.environ.get("INTERNAL_API_SECRET_KEY"):
        tidb.reconnect()
        tidb_cursor = tidb.cursor()
        sql = "SELECT * FROM asknotes.users"
        tidb_cursor.execute(sql)
        user_result = tidb_cursor.fetchall()
        for user in user_result:
            user_id = user[0]
            notion_api = NotionAPI(user[1])
            courses_id = user[3]
            courses_db = notion_api.query_database(courses_id, {})
            course_last_edited_time = courses_db["results"][0]["last_edited_time"]
            if course_last_edited_time != user[6]:
                courses_query = notion_api.query_database(courses_id, {
                    "filter": {
                        "property": "Course Materials",
                        "files": {
                            "is_not_empty": True
                        }
                    }
                })
                for course in courses_query["results"]:
                    course_name = course["properties"]["Name"]["title"][0]["plain_text"]
                    folder_uuid = uuid.uuid4()
                    temp_folder = f"./user_content/temp/{folder_uuid}"
                    os.mkdir(temp_folder)
                    for material in course["properties"]["Course Materials"]["files"]:
                        material_name = material["name"]
                        material_url = material["file"]["url"]
                        urllib.request.urlretrieve(material_url, f"{temp_folder}/{material_name}")
                    documents = SimpleDirectoryReader(temp_folder).load_data()
                    for idx, document in enumerate(documents):
                        document.metadata = {"course": course_name}
                    tidbvec = TiDBVectorStore(
                        connection_string=os.getenv("EMBEDDINGS_TIDB_CONNECTION_URL"),
                        table_name=user_id,
                        distance_strategy="cosine",
                        vector_dimension=1536,  #768,
                        drop_existing_table=False,
                    )
                    storage_context = StorageContext.from_defaults(vector_store=tidbvec)
                    VectorStoreIndex.from_documents(
                        documents, storage_context=storage_context, embed_model=embed_model, show_progress=True
                    )
                    shutil.rmtree(temp_folder)
                sql = "UPDATE asknotes.users SET courses_last_updated = %s WHERE id = %s"
                val = (course_last_edited_time, user_id)
                tidb_cursor.execute(sql, val)
                tidb.commit()
        return ""
    else:
        return "Unauthorized. Please <a href='/'>Sign In</a>"


@app.route("/chat", methods=["GET"])
def chat():
    supabase_session = supabase.auth.get_session()
    if supabase_session:
        return render_template("chat.html")
    else:
        return "Unauthorized. Please <a href='/'>Sign In</a>"


@app.route("/chat/query", methods=["POST"])
def chat_query():
    supabase_session = supabase.auth.get_session()
    if supabase_session:
        tidb.reconnect()
        tidb_cursor = tidb.cursor()
        notion_user_id = supabase_session.user.user_metadata.get("sub")
        tidbvec = TiDBVectorStore(
            connection_string=os.getenv("EMBEDDINGS_TIDB_CONNECTION_URL"),
            table_name=notion_user_id,
            distance_strategy="cosine",
            vector_dimension=1536,  # 768,
            drop_existing_table=False,
        )
        request_body = request.json
        chat_id = request_body["chat_id"]
        query = request_body["query"]
        if chat_id:
            sql = f"SELECT M.id, M.chat_id, M.role, M.content, M.sequence, C.user_id, M.created_at FROM asknotes.messages M INNER JOIN asknotes.chats C ON C.id = M.chat_id WHERE chat_id = %s AND user_id = %s ORDER BY sequence ASC;"
            val = (chat_id, notion_user_id)
            tidb_cursor.execute(sql, val)
            messages = tidb_cursor.fetchall()
            if messages:
                '''
                formatted_messages = []
                for msg in messages:
                    formatted_messages.append({"role": msg[2], "content": msg[3]})
                '''
                vector_store_index = VectorStoreIndex.from_vector_store(vector_store=tidbvec, embed_model=embed_model)
                query_engine = vector_store_index.as_query_engine()
                response = query_engine.query(query)
                response = str(response)
                sql = "INSERT INTO asknotes.messages (id, chat_id, role, content, sequence, created_at) VALUES (%s, %s, %s, %s, %s, %s)"
                val = (str(uuid.uuid4()), chat_id, "user", query, messages[-1][4] + 1,
                       datetime.datetime.now(datetime.UTC).timestamp())
                tidb_cursor.execute(sql, val)
                sql = "INSERT INTO asknotes.messages (id, chat_id, role, content, sequence, created_at) VALUES (%s, %s, %s, %s, %s, %s)"
                val = (str(uuid.uuid4()), chat_id, "assistant", response, messages[-1][4] + 2,
                       datetime.datetime.now(datetime.UTC).timestamp())
                tidb_cursor.execute(sql, val)
                tidb.commit()
                tidb_cursor.close()
                return json.dumps({
                    "ok": True,
                    "chat_id": chat_id,
                    "response": response
                })
            else:
                return json.dumps({
                    "ok": False,
                    "error": "Chat not found"
                })
        else:
            sql = "INSERT INTO asknotes.chats (id, user_id, created_at) VALUES (%s, %s, %s)"
            chat_id = str(uuid.uuid4())
            val = (chat_id, notion_user_id, datetime.datetime.now(datetime.UTC).timestamp())
            tidb_cursor.execute(sql, val)
            system_message = "You are AskNotes Pal, a helpful assistant. Your purpose is to help answer the student's question. Whenever possible, use the context, documents, embeddings, or vectors that you have been given to answer the student's questions."
            intro_message = "Hi, I am AskNotes Pal, your virtual pal! Ask me anything about your course notes!"
            sql = "INSERT INTO asknotes.messages (id, chat_id, role, content, sequence, created_at) VALUES (%s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s)"
            val = (
            str(uuid.uuid4()), chat_id, "system", system_message, 0, datetime.datetime.now(datetime.UTC).timestamp(),
            str(uuid.uuid4()), chat_id, "assistant", intro_message, 1, datetime.datetime.now(datetime.UTC).timestamp(),
            str(uuid.uuid4()), chat_id, "user", query, 2, datetime.datetime.now(datetime.UTC).timestamp())
            tidb_cursor.execute(sql, val)
            vector_store_index = VectorStoreIndex.from_vector_store(vector_store=tidbvec, embed_model=embed_model)
            query_engine = vector_store_index.as_query_engine()
            response = query_engine.query(query)
            response = str(response)
            sql = "INSERT INTO asknotes.messages (id, chat_id, role, content, sequence, created_at) VALUES (%s, %s, %s, %s, %s, %s)"
            val = (
            str(uuid.uuid4()), chat_id, "assistant", response, 3, datetime.datetime.now(datetime.UTC).timestamp())
            tidb_cursor.execute(sql, val)
            tidb.commit()
            tidb_cursor.close()
            return json.dumps({
                "ok": True,
                "chat_id": chat_id,
                "response": response
            })
    else:
        return "Unauthorized. Please <a href='/'>Sign In</a>"


if __name__ == "__main__":
    ssl_context = ('cert.pem', 'key.pem')
    app.run(host="0.0.0.0", port=5000, ssl_context=ssl_context)
