# Owner handoff

The delivery archive contains the project and its hidden `.git` directory, including the local commit and prior history. It excludes local databases, virtual environments, logs, coverage data and temporary browser artifacts.

1. Extract the complete `lunchpicker` folder, including `.git`.
2. Review the changes and requirement mapping:

   ```sh
   git status
   git log -1 --format=fuller
   git show --stat HEAD
   ```

3. Run the application/checks using `README.md`; results are recorded in `docs/VERIFICATION.md`.
4. When ready, push using your own GitHub credentials:

   ```sh
   git push origin main
   ```

The local Git author/committer identity matches the repository's existing Sabina commits: `Sabinaa-Isayeva <not.s12ina@gmail.com>`. No remote push was performed. Local commit attribution does not authenticate a GitHub account; the owner uses their own credentials when pushing.

If the remote branch has advanced, fetch and review those commits before rebasing or merging this local change. The repository origin remains `https://github.com/Sabinaa-Isayeva/lunchpicker.git`.
