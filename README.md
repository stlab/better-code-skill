# Better Code skills

Better Code is a collection of skills for GitHub Copilot CLI. It guides coding,
contract drafting, writing, algorithm research, and work tracking. The skills depend on
Superpowers and Technical Documentation; install both companions before using
the Better Code plugin.

## Prerequisites

Install [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
and Node.js 22.20 or later.

Install [Superpowers](https://github.com/obra/superpowers) using its marketplace:

```bash
copilot plugin marketplace add obra/superpowers-marketplace
copilot plugin install superpowers@superpowers-marketplace
```

Install [Technical Documentation](https://skills.wondel.ai/skills/technical-documentation/)
for Copilot:

```bash
npx skills add wondelai/skills --skill technical-documentation --global --agent github-copilot
```

## Install Better Code

Register the marketplace and install the plugin:

```bash
copilot plugin marketplace add stlab/better-code-skill
copilot plugin install better-code@better-code-marketplace
```

Run `copilot skill list` to check that the plugin's five skills are available.
Copilot may display the short skill names in this list. Start a new Copilot
session after installation.

## Skills

The plugin provides these namespaced skills:

- `better-code:better-code`: guidance for correct, efficient, reusable code.
- `better-code:contracts`: drafting and formatting declaration contracts.
- `better-code:writing`: clear prose, comments, and documentation.
- `better-code:algorithm-research`: research standard algorithms and libraries
  after implementation planning.
- `better-code:doing`: track started work across repositories and sessions.

Better Code invokes Superpowers for development process and its own Writing and
Contracts skills when needed. Writing invokes Technical Documentation for
developer documentation other than declaration contracts. Algorithm Research
complements Superpowers' planning workflow. Install the companions separately;
installing Better Code does not install them.

If you previously installed standalone copies of these skills, remove or disable
the duplicates to avoid ambiguous skill names.

## Track work

Doing keeps a Markdown checklist in `~/.better-code/doing.md`. It records started
work, not a backlog, and keeps completed entries. The file contains task
descriptions, locations, and session details in plaintext on your computer.
Don't include secrets in descriptions.

The skill asks the agent to track multistep tasks automatically. Automatic
tracking depends on the agent discovering and following the skill and having
permission to write the file. The helper requires Python 3.9 or later and a
filesystem that supports POSIX directory locking; it has been tested on macOS.

In Copilot, you can invoke the skill explicitly:

```text
/better-code:doing
/better-code:doing show
/better-code:doing show all
/better-code:doing task Investigate the parser
/better-code:doing done
```

The slash-command picker shows `show [all] | task <DESCRIPTION> | done` beside the skill.

Invoking the skill without arguments or with `show` lists open work; `show all`
includes completed work. If the current task
can't be identified safely, the agent asks which task to complete. Session and
tmux details are recorded only when available.

## Update

Update the Better Code and Superpowers marketplace catalogs and plugins:

```bash
copilot plugin marketplace update better-code-marketplace
copilot plugin update better-code@better-code-marketplace
copilot plugin marketplace update superpowers-marketplace
copilot plugin update superpowers@superpowers-marketplace
```

Update Technical Documentation with the same tool used to install it:

```bash
npx skills update --global technical-documentation
```

Start a new Copilot session to use the updated skills.

## License

[Boost Software License 1.0](LICENSE).
