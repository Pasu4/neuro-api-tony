# Neuro API Human Control

Graphical implementation of the Neuro API in python.
Like [Randy](https://github.com/VedalAI/neuro-game-sdk/blob/main/Randy), it can answer `actions/force` commands automatically, but also allows the user to formulate the response Neuro would send themselves, as well as send non-forced actions whenever.

> [!Note]
> I cannot guarantee that this implementation perfectly emulates what Neuro could/would do, or that it is error-free.
> There might be some things that I have overlooked.

## Installation

This will install the package in a virtual environment to not conflict with any global packages.
Skip steps 2 and 3 if you don't want a virtual environment.
**All commands after step 1 should be run in the downloaded folder.**

1. Clone the repository with `git clone https://github.com/Pasu4/neuro-api-human-control.git` or download it from GitHub
2. Run `python -m venv .venv`
3. Run `.\.venv\Scripts\activate` on Windows, or `source ./.venv/bin/activate` on Linux / Mac
4. Run `pip install -r requirements.txt`

## Updating

This assumes you have cloned the repository with git.
If you didn't, you're better off re-downloading and re-installing than updating the files manually.
**All commands should be run in the folder of the application.**

1. Run `git pull`
2. Run `.\.venv\Scripts\activate` on Windows, or `source ./.venv/bin/activate` on Linux / Mac (Skip this step if you didn't set up a virtual environment)
3. Run `pip install -r requirements.txt` to install any potential new dependencies

## Usage

This assumes you have set up a virtual environment during installation.
Skip step 1 if you haven't, or if your virtual environment is already activated.
**All commands should be run in the folder of the application.**

1. Run `.\.venv\Scripts\activate` on Windows, or `source ./.venv/bin/activate` on Linux / Mac
2. Run `python -m src`

The application window should now open.
The left panel will display the actions once they have been registered.
They can be executed by clicking the "execute" button next to the action's name.
The right panel shows an event log, below that is a smaller panel with some controls.
After sending an `action` command to the game, the next action can only be sent after the `action/result` command has been received.
When the game sends an `actions/force` command, a window will open that only shows the applicable actions, and will only close once the `action/result` command indicates success.

Like Randy, this application opens a websocket server on port `8000` (websocket URL `ws://localhost:8000`).

> [!Note]
> When working with the Unity SDK, you need to focus the Unity editor after sending an action for the game to receive the action.

### Executing actions

To execute an action, the game first needs to send an `actions/register` command.
After that, an entry should appear in the left panel showing the name of the action and an "Execute" button.
Clicking on the button opens a window where you can enter the content of the reply and send it via the "Send" button.
The window will already contain some sample JSON that validates against the schema.
By default, your input will be parsed and validated against the schema before sending, you can turn this off in the control panel.

If an `actions/force` command is received, a "Forced action" window will open, showing all applicable actions and the query and state of the command.
Executing actions from here works the same as from the main actions panel.
Once the game has acknowledged the sent action with an action result, the window will close automatically.
You can also close the window manually, this will ignore the forced action and allow you to execute any registered action.

### Logs

The log panel on the top right has three different tabs:

- The **log tab** logs all commands that are received and sent, without showing their content. It also shows error messages and warnings in red.
- The **context tab** shows everything that Neuro would get to read directly, which is the content of `context` commands, the state and query of `actions/force` commands, and the message of `action/result` commands. Silent and ephemeral contexts are diplayed in gray.
- The **network tab** shows the full data sent over the websocket, as well as who sent that data. If it is valid JSON, it will be formatted for easier viewing.

### Control panel

#### Normal controls

The control panel has some checkboxes and buttons that change the behavior of the application.

- **Validate JSON schema:** If checked, will not allow you to send a message that does not validate against the schema.
- **Ignore forced actions:** If checked, will not open the "Forced action" dialog when an `actions/force` command is received. You have to execute the action yourself from the left panel. Since the forced action is ignored, you can execute any registered action.
- **Automatically answer forced actions**: If checked, will immediately send the pre-generated JSON of a random valid action instead of opening the "Forced action" window when an `actions/force` command arrives. This behavior is similar to what Randy does.

#### Experimental controls

These controls are [proposed features](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md) in the Neuro API that will likely not work unless specifically implemented. Use at your own risk!

- **Clear all actions and request reregistration (experimental):** Will unregister all currently registered actions and send an [`actions/reregister_all`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#reregister-all-actions) command to the game.
- **Request graceful shutdown (experimental):** Will send a [`shutdown/graceful`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#graceful-shutdown) command to the game, indicating it should save the game and return to the main menu at the next opportunity.
- **Cancel graceful shutdown (experimental):** Will send a [`shutdown/graceful`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#graceful-shutdown) command with its `wants_shutdown` field set to `false` to the game, indicating to cancel a previous shutdown request.
- **Request immediate shutdown (experimental):** Will send a [`shutdown/immediate`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md#immediate-shutdown) command to the game, indication that the game *will* (not *should*!) be shut down within the next few seconds.

## Screenshots

![Image of the application](image.png)

![Another image of the application](image-1.png)
