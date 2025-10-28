/** @import { NeuroClient } from 'neuro-game-sdk'; */
const { NeuroClient } = NeuroGameSdk;

/** @type {NeuroClient} */
let neuroClient = null;

const commands = [
    // { name: 'startup', handler: sendStartup },
    { name: 'context', handler: sendContext },
    { name: 'register', handler: sendRegister },
    { name: 'unregister', handler: sendUnregister },
    { name: 'force', handler: sendForce },
    { name: 'result', handler: sendResult },
    // { name: 'raw', handler: sendRaw },
]

document.addEventListener('DOMContentLoaded', () => {
    /** @type {HTMLSpanElement} */
    const connectionStatusSpan = document.getElementById('connection-status');
    /** @type {HTMLInputElement} */
    const apiUrlField = document.getElementById('connect-url-text');
    /** @type {HTMLInputElement} */
    const gameNameField = document.getElementById('connect-game-text');

    for (const command of commands) {
        /** @type {HTMLFormElement} */
        const form = document.getElementById(`${command.name}-form`);
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            command.handler(mapFormElements(form.elements));
        });
    }

    document.getElementById('connect-button').addEventListener('click', () => {
        neuroClient?.disconnect();
        const apiUrl = apiUrlField.value;
        const gameName = gameNameField.value;

        neuroClient = new NeuroClient(apiUrl, gameName, () => {
            connectionStatusSpan.textContent = 'Status: Connected';
            connectionStatusSpan.classList.remove('connecting');
            connectionStatusSpan.classList.add('connected');

            neuroClient.onAction(actionHandler);
        });

        connectionStatusSpan.textContent = 'Status: Connecting...';
        connectionStatusSpan.classList.remove('disconnected');
        connectionStatusSpan.classList.add('connecting');
        neuroClient.onClose = () => {
            connectionStatusSpan.textContent = 'Status: Disconnected';
            connectionStatusSpan.classList.remove('connecting', 'connected');
            connectionStatusSpan.classList.add('disconnected');
        };
    });

    document.getElementById('disconnect-button').addEventListener('click', () => {
        neuroClient?.disconnect();
        neuroClient = null;
    });
});

// function sendStartup(data) {
//     console.log(data);
// }

function sendContext(data) {
    neuroClient?.sendContext(data.message, data.silent);
}

function sendRegister(data) {
    data.schema = JSON.parse(data.schema);
    neuroClient?.registerActions([data]);
}

function sendUnregister(data) {
    names = data.action_names.split(',').map(name => name.trim());
    neuroClient?.unregisterActions(names);
}

function sendForce(data) {
    names = data.action_names.split(',').map(name => name.trim());
    neuroClient?.forceActions(data.query, names, data.state, data.ephemeral_context);
}

function sendResult(data) {
    neuroClient?.sendActionResult(data.id, data.success, data.message);
}

// function sendRaw(data) {
//     console.log(data);
// }

/**
 * @param {{ id: string; name: string; params: any;}} action
 */
function actionHandler(action) {
    console.log('Received action:', action);
    if(window.confirm(`Action received:\n${JSON.stringify(action, null, 2)}\n\nSend success result?`)) {
        neuroClient?.sendActionResult(action.id, true, 'Action completed successfully.');
    }
}

/**
 * @param {HTMLFormControlsCollection} formElements
 * @returns {Record<string, string>}
 */
function mapFormElements(formElements) {
    const result = {};
    for (const element of formElements) {
        if (element.type === 'checkbox')
            result[element.name] = element.checked;
        else if (element.name)
            result[element.name] = element.value;
    }
    return result;
}
