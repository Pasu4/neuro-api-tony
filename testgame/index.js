/**
 * @import { NeuroClient } from 'neuro-game-sdk';
 */
const { NeuroClient } = NeuroGameSdk;

const NEURO_SERVER_URL = 'ws://localhost:8000';
const GAME_NAME = 'Test Game';

/** @type {NeuroClient} */
var neuroClient = undefined;
var username = undefined;
var connected = false;

document.addEventListener('DOMContentLoaded', () => {
    /** @type {HTMLFormElement} */
    const usernameForm = document.getElementById('user-form');
    usernameForm.addEventListener('submit', (event) => {
        event.preventDefault();
        username = usernameForm.elements['username'].value;
        userColor = usernameForm.elements['user-color'].value;
        usernameForm.style.display = 'none';
        document.getElementById('game').style.display = 'block';

        initNeuroClient();
    });

    /** @type {HTMLFormElement} */
    const chatForm = document.getElementById('chat-form');
    chatForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const message = chatForm.elements['chat-input'].value;
        chatForm.elements['chat-input'].value = '';
        if (connected) {
            neuroClient.sendContext(username + ' says: ' + message);
            addChatMessage(username, userColor, message);
        }
    });

    /** @type {HTMLFormElement} */
    const actionForm = document.getElementById('action-form');
    actionForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (connected) {
            actionName = actionForm.elements['action-name'].value;
            actionForm.elements['action-name'].value = '';
            addChatMessage('System', '#ff0000', 'Registering action: ' + actionName);

            neuroClient.registerActions([{
                name: actionName,
                description: actionForm.elements['action-description'].value,
                schema: JSON.parse(actionForm.elements['action-schema'].value)
            }]);

            neuroClient.onAction(actionData => {
                if (actionData.name === actionName) {
                    addChatMessage('System', '#ff0000', 'Action received: ' + actionData.name + '\n' + JSON.stringify(actionData.params));
                    neuroClient.sendActionResult(actionData.id, true);
                }
            });
        }
    });
});

function initNeuroClient() {
    neuroClient = new NeuroClient(NEURO_SERVER_URL, GAME_NAME, () => {
        addChatMessage('System', "#ff0000", 'Connected to Neuro');

        neuroClient.registerActions([{
            name: 'send_chat_message',
            description: 'Send a chat message to ' + username,
            schema: {
                type: 'object',
                properties: {
                    message: { type: 'string' }
                },
                required: ['message']
            }
        }]);

        neuroClient.onAction(actionData => {
            if(actionData.name === 'send_chat_message') {
                addChatMessage('Neuro', '#c97baf', actionData.params.message);
                neuroClient.sendActionResult(actionData.id, true);
            }
        })

        connected = true;
    });
}

function addChatMessage(author, color, message) {
    const chat = document.getElementById('chat-messages-container');
    const messageElement = document.createElement('div');
    messageElement.className = 'chat-message';

    const authorElement = document.createElement('span');
    authorElement.className = 'chat-message-author';
    authorElement.style.color = color;
    authorElement.innerText = '<' + author + '>';
    messageElement.appendChild(authorElement);

    const messageText = document.createElement('span');
    messageText.className = 'chat-message-text';
    messageText.innerText = ' ' + message;
    messageElement.appendChild(messageText);

    chat.appendChild(messageElement);
}

var randomAction = 'send_chat_message';

function registerRandomAction() {
    const actionName = 'action_' + Math.floor(Math.random() * 1000000).toString();
    randomAction = actionName;
    neuroClient.registerActions([{
        name: actionName,
        description: 'Random action'
    }]);
}

function forceRandomAction() {
    neuroClient.forceActions('Execute an action', [randomAction]);
}

function sendSuccess() {
    neuroClient.sendActionResult('random_id', true);
}

function sendFailure() {
    neuroClient.sendActionResult('random_id', false);
}
