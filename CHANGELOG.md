# Changelog

This changelog lists mainly functional changes, most refactoring PRs after v2.0.0 will only be listed in the [Releases](https://github.com/Pasu4/neuro-api-tony/releases) section of the repository.

## 2.0.0

Exactly one year after v1.0.0 btw

- Replaced the old JSON editor with [a new one](https://github.com/Pasu4/neuro-api-tony/tree/master?tab=readme-ov-file#json-editor) that is more suitable for editing code.
- Finished support for multiple client connections.
- Added the possibility to use a [configuration file](https://github.com/Pasu4/neuro-api-tony/tree/master?tab=readme-ov-file#configuration). For a full list of what can be configured, look at [the schema](https://github.com/Pasu4/neuro-api-tony/blob/0007488b256f0c4e1f69cb7d9321296ef90a1487/tony-config.schema.json) or use VS Code's IntelliSense.
- fix a bug that mismatched actions by @KTrain5169 in https://github.com/Pasu4/neuro-api-tony/pull/32
- Fall back basic generator when JSF fails by @Mixone-FinallyHere in https://github.com/Pasu4/neuro-api-tony/pull/35
- make a start on removing Any types from the codebase by @KTrain5169 in https://github.com/Pasu4/neuro-api-tony/pull/36
- Replace type `dict[str, Any]` for an action's schema with Neuro-API's SchemaObject type by @KTrain5169 in https://github.com/Pasu4/neuro-api-tony/pull/39

## 1.6.4

- Fixed https://github.com/Pasu4/neuro-api-tony/issues/34

## 1.6.3

- Switch to Neuro-API and start on multi-client support by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/28
- Make game client id monotonic and start on passing client id everywhere by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/29
- [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci[bot] in https://github.com/Pasu4/neuro-api-tony/pull/31
- Fixed https://github.com/Pasu4/neuro-api-tony/issues/33

## 1.6.2

- Ignore zizmor hash pinnning by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/23
- [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci[bot] in https://github.com/Pasu4/neuro-api-tony/pull/22
- 2025-07-29 Neuro API updates by @KTrain5169 in https://github.com/Pasu4/neuro-api-tony/pull/24
    - Added `multipleOf` and `uniqueItems` to the list of unsupported schema keys
    - Changed warning message for unsupported schema keys
- Update dependencies by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/25

## 1.6.1

- Added an error message for unknown command line arguments
- Added `--host` as an alias for `--addr`
- Documented some API methods and callbacks
- Fixed still registering actions that were detected as invalid
- Fixed handling of null and boolean schemas

## 1.6.0

- Tony now remembers the last sent action data for every action
- Made API work with other event loops (like asyncio) so it can be used in other projects
    - Documentation for the API functions will be added soon™
- Batched logging of action registration / unregistration to reduce clutter
- Non-specification-compliant user action log messages changed from warnings to infos
- Added an info message when a client sends the startup message
- Made additional context in the command log gray to highlight the actual command
- Switch to `crateci/typos` mirror and update test dependencies by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/20

## 1.5.5

- Fixed action window still validating even if "Don't validate" is checked.

## 1.5.4

- Fixed forced action window not opening when the state is undefined.

## 1.5.3

- Forced action state is now formatted as JSON
- Fixed critical error highlighting

## 1.5.2

- Added line-wrapped action description below action list
- Forced action window text now wraps properly
- PR: Upgrade Dependencies by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/18

## 1.5.1

- Fixed command log not clearing
- Fixed log clearing not removing highlight

## 1.5.0

- Actions can now be executed by double-clicking
- Improved action dialog
- Moved log controls to log panel
- Moved action validation control to action dialog
- Most buttons are now only enabled when applicable
- Changed some button names and tooltips

## 1.4.2

- Added a button to delete all actions
- Changed a few log colors for better visibility

## 1.4.1

- Fixed incorrect label on millisecond precision toggle

## 1.4.0

- Added an icon notification when there is a warning or error in the system tab
- Add an option for microsecond precision timestamps
- Made control panel more compact
- Changed layout of forced action window (again)

## 1.3.0

- Added live schema validation
- Added button to regenerate json
- Added more tooltips
- Added a button to maximize the log panel
- Added a warning when an actions/force arrived while another is still active
- Updated documentation
- Made more dialogs resizable
- Improved schema display
- Fixed log level not working
- Fixed text overflow with long queries and states

## 1.2.0

- PR: Format code with `ruff format` by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/16
- Added separate log panels for system and command
- Added tooltips to controls, and made labels shorter
- Added log file export
- Fixed `--help` and `--version` not working
- Fixed the update notification not showing (now shows in the system log)
- Fixed formatting for unknown commands
- Fixed silent error when starting multiple instances

## 1.1.4

- Ruff linting by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/15
- Add tests for api and model by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/14
- Fix sending action without data by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/17

## 1.1.3

- Remove unneeded threading lock by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/11
- Fix project requirements by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/10
- Continuous integration by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/9
- Make sure async run is shut down cleanly before closing application by @CoolCat467 in https://github.com/Pasu4/neuro-api-tony/pull/13
- Fix https://github.com/Pasu4/neuro-api-tony/pull/12 (Errors on empty data schema)

## 1.1.2

- Re-implemented update checking

## 1.1.1

- Fixed `__main__.py` in site-packages

## 1.1.0

- added: Everything
