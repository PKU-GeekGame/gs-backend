# Project Guiding Star: The Backend

It is a part of the Guiding Star project.
[Learn more about the overall architecture here.](https://github.com/pku-GeekGame/guiding-star)

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

## Usage

The backend codebase is compatible with Linux and Windows.

Although nobody uses Windows on a server, it is a good news if you develop on Windows. 

**Setup:**

- Install Python (≥3.8)
- `pip install -r requirements.txt`
- Install MySQL server (≥5.7.8, or MariaDB ≥10.2.7 for the JSON datatype) and set up a database
  - `CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';`
  - `CREATE DATABASE database;`
  - `GRANT ALL PRIVILEGES ON database.* TO 'username'@'localhost';`
  - `FLUSH PRIVILEGES;`
- Configure parameters
  - Rename `src/secret_example.py` to `src/secret.py`
  - Fill in everything in that file
    - And create directories mentioned in the file
- Prepare the database
  - Set environment variable: `export FLASK_APP=src/admin/app`
  - `flask db init`
  - `flask db migrate`
  - The above command will complain about the circular dependency of two constraints (`SAWarning: Cannot correctly sort tables; there are unresolvable cycles between tables "user, user_profile" ...`).
    You need to manually tweak the generated Python file in `migrations/versions`  
    - Comment out the line `sa.ForeignKeyConstraint(['profile_id'], ['user_profile.id'], ),`
    - Insert `op.create_foreign_key(None, 'user', 'user_profile', ['profile_id'], ['id'])` at the end of the `upgrade` method
  - `flask db upgrade`

**Start the server:**

- `python3 run_reducer_admin.py`
  - It will show `[success] reducer.mainloop: started to receive actions`
- `python3 run_worker_api.py`
  - It will show `[success] worker.mainloop: started to receive events`

It is a good idea to run them as a systemd service on the deployment server.
You should put these services behind a reverse proxy. [Refer to setup instruction here](https://github.com/pku-GeekGame/guiding-star).

**Development:**

- `pip install -r requirements-dev.txt`
  - This will install `mypy` and type sheds
- To type-check the code, run `python3 -m mypy.dmypy run`
- We recommend Python IDEs that give accurate completions with type hints
  - i.e. PyCharm

## License

This repository is distributed under [MIT License](LICENSE.md).