# gomod-go-version-updater-action

创建此 Action 的原因是 [Dependabot 无法](https://github.com/dependabot/dependabot-core/issues/9057) 更新 `go.mod` 文件中定义的 Go 版本。

## 使用方法

1. 要使用此 Action，请确保在 Action 设置中启用了 `Allow GitHub Actions to create and approve pull requests`（允许 GitHub Actions 创建和批准拉取请求）选项。您可以通过在项目 URL 后附加 `/settings/actions` 来找到该设置，例如：
   `https://github.com/<owner>/<project-name>/settings/actions`。
2. 启用该设置后，创建 `~/.github/workflows/gomod-go-version-updater.yml` 文件，内容如下：
   ```yml
   ---
   name: gomod-go-version-updater-action
   "on":
     schedule:
       - cron: "42 6 * * *"
   permissions:
     contents: write
     pull-requests: write
   jobs:
     gomod-go-version-updater-action:
       runs-on: ubuntu-22.04
       steps:
         - uses: 030/gomod-go-version-updater-action@v0.1.6
   ```
3. 为了确保能够触发 Action 以测试 Golang 版本更新，请添加 `pull_request_review` 触发器。这将使得每当有人对 **gomod-go-version-updater-action** 创建的拉取请求提交评审时，都会运行特定的 Workflow Action：
   ```yml
   "on":
     # gomod-go-version-updater 需要此项以便在 PR 被评审后触发此 Action
     pull_request_review:
       types: [submitted]
   ```
4. 可选：如果需要下载私有 Go 模块：
   ```yml
   - uses: 030/gomod-go-version-updater-action@v0.1.6
     with:
       github-token-for-downloading-private-go-modules: ${{ secrets.GITHUB_TOKEN }}
   ```
5. 可选：将日志级别设置为 `DEBUG`、`WARNING`、`ERROR` 或 `CRITICAL`（默认值：INFO）：
   ```yml
   - uses: 030/gomod-go-version-updater-action@v0.1.6
     with:
       gomod-go-version-updater-action-log-level: DEBUG
   ```
6. 可选：为将要创建的 PR 添加额外标签：
   ```yml
   - uses: 030/gomod-go-version-updater-action@v0.1.6
     with:
       extra-pr-label: something
   ```

## 开发

如果您想开发此 Action，可能需要使用虚拟环境。您可以随心所欲地配置，但最简单的方法是运行：

```python
python3 -m venv .venv
```

随后不要忘记激活虚拟环境：

```bash
source .venv/bin/activate
```

要安装用于项目开发的依赖项，可以使用 `pip`：

```bash
pip install '.[dev]'
```

要运行测试套件，请执行：
```bash
pytest
```

## 测试

除了使用 `pytest` 运行的测试套件（见上文）外，我们还作为质量控制的一部分运行了一套更广泛的测试。详情请参阅 [此 GitHub Workflow](.github/workflows/python.yml) 中定义的运行步骤。
