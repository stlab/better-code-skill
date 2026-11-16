# Better Code skills

Better Code is a collection of skills for GitHub Copilot CLI. It guides coding,
contract drafting, writing, and algorithm research. The skills depend on
Superpowers and Technical Documentation; install both companions before using
the Better Code plugin.

## Prerequisites

Install [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/quickstart)
and Node.js 22.20 or later.

Install [Superpowers](https://github.com/obra/superpowers) using its marketplace:

```bash
copilot plugin marketplace add obra/superpowers-marketplace
copilot plugin install superpowers@superpowers-marketplace
```

Install [Technical Documentation](https://skills.wondel.ai/skills/technical-documentation/)
for Copilot:

```bash
npx skills add wondelai/skills/technical-documentation --global --agent github-copilot
```

## Install Better Code

Register the marketplace and install the plugin:

```bash
copilot plugin marketplace add stlab/better-code-skill
copilot plugin install better-code@better-code-marketplace
```

Run `copilot skill list` to check that the plugin's four skills are available.
Copilot may display the short skill names in this list. Start a new Copilot
session after installation.

## Skills

The plugin provides these namespaced skills:

- `better-code:better-code`: guidance for correct, efficient, reusable code.
- `better-code:contracts`: drafting and formatting declaration contracts.
- `better-code:writing`: clear prose, comments, and documentation.
- `better-code:algorithm-research`: research standard algorithms and libraries
  after implementation planning.

Better Code invokes Superpowers for development process and its own Writing and
Contracts skills when needed. Writing invokes Technical Documentation for
developer documentation other than declaration contracts. Algorithm Research
complements Superpowers' planning workflow. Install the companions separately;
installing Better Code does not install them.

If you previously installed standalone copies of these skills, remove or disable
the duplicates to avoid ambiguous skill names.

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
