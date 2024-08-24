const currentTimeFormatted = `${new Date().getHours().toString().padStart(2, "0")}:${new Date().getMinutes().toString().padStart(2, "0")}`;
const messageWindow = document.getElementById("messageWindow");
const queryForm = document.getElementById("queryForm");
const queryField = document.getElementById("queryField");
const sendButton = document.getElementById("sendButton");
const queryWait = document.getElementById("queryWait");
document.getElementById("message-1-time").innerText = currentTimeFormatted;

messageCount = 1;

function appendChatBubble(message, role) {
    sanitizedMessage = HtmlSanitizer.SanitizeHtml(message);
    html = "";
    messageCount += 1;
    if (role === "assistant") {
        html = `
        <div class="box p-3 has-background-grey-darker ml-2 chat-bubble-left">
            <span id="message-${messageCount}-content" class="has-text-light"><i class="fa-solid fa-spinner spinner"></i> Processing</span>
            <div class="is-flex is-justify-content-space-between has-text-grey-light is-size-7 mt-2">
                <span>AskNotes Pal</span>
                <span>${currentTimeFormatted}</span>
            </div>
        </div>
        `
    } else if (role === "user") {
        html = `
        <div class="box p-3 has-background-grey is-align-self-flex-end mr-2 chat-bubble-right">
            <span id="message-${messageCount}-content" class="has-text-light">${sanitizedMessage}</span>
            <div class="is-flex is-justify-content-space-between has-text-grey-light is-size-7 mt-2">
                <span>You</span>
                <span>${currentTimeFormatted}</span>
            </div>
        </div>
        `;
    };
    messageWindow.innerHTML += html;
    messageWindow.scrollTop = messageWindow.scrollHeight;
};

function disableQuery() {
    queryField.setAttribute("disabled", "true");
    sendButton.classList.add("is-hidden");
    queryWait.classList.remove("is-hidden");
};

function enableQuery() {
    queryField.removeAttribute("disabled");
    queryWait.classList.add("is-hidden");
    sendButton.classList.remove("is-hidden");
};

function callQueryApi(query) {
    const searchParams = new URLSearchParams(window.location.search)
    const chat_id = searchParams.get("chat_id");
    fetch("/chat/query", {
        method: "POST",
        body: JSON.stringify({
            query,
            chat_id
        }),
        headers: {
            "Content-Type": "application/json"
        }
    }).then(res => res.json()).then(res => {
        if (res.ok) {
            console.log("query ok")
            window.history.replaceState(null, null, `?chat_id=${res.chat_id}`);
            document.getElementById(`message-${messageCount}-content`).innerText = res.response;
            messageWindow.scrollTop = messageWindow.scrollHeight;
            enableQuery();
        } else {
            document.getElementById(`message-${messageCount}-content`).innerText = "Sorry, an error occurred when processing your query";
        };
    }).catch(err => {
        document.getElementById(`message-${messageCount}-content`).innerText = "Sorry, an error occurred when processing your query";
    });
};

function processQuery() {
    const formData = new FormData(queryForm);
    const query = formData.get("query");
    if (queryField.value) {
        appendChatBubble(query, "user")
        callQueryApi(query);
        queryField.value = "";
        appendChatBubble("", "assistant")
    };
};