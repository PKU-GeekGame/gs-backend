# Project Guiding Star: The Backend

## Highlights

- **Not configurable is most customizable.** Every contest has its unique rule, which is unlikely to be fully covered
  by a text file or SQL table. Our experience shows that these static configurations
  often disturb contest organizers when they want more customization. Instead, we trust them as decent programmers,
  leaving the customization to the logic in the source code that is easy to maintain and extend.
- **Pure Python Logic.** The core logic that handles submissions, scoreboards, and users are written in plain old Python.
  Only basic Object-Oriented Programming skill is required before you can start customization.
  No preknowledge of heavy third-party frameworks is needed.
- **Type-checked.** Every function in the codebase is type-annotated and checked by Mypy in strict mode.
  With type information, you can reliably auto-complete the code and check what breaks after a refactor in a capable IDE.
- **A flexible state machine.** The logic splits into one *reducer* that updates the game state and
  multiple *workers* that power read-only APIs and pass actions to the reducer.
  The state synchronizes in real-time with ZeroMQ sockets.
  It is easy to attach different kinds of workers that handle push notifications or background jobs to the reducer.
- **Scalable performance.** A bonus of the state machine architecture is that only raw submissions are in the database
  (so that the state can be restored after a service restart).
  The game state is kept in RAM, making it more performant when updating the scoreboard.
  The backend is also asynchronous, therefore a laggy OAuth provider will not block other requests.

## Architecture

TODO

## License

This repository is licensed under [AGPLv3](LICENSE.md) by default.

If you want to use this project but the modified source code cannot be published (which violates AGPL) for some reason,
you may request for a more relaxed license, but there is no guarantee that every request will be granted.