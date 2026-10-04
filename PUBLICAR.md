# Como publicar o projeto 2 (ordem importa)

Tempo estimado: 40 a 60 minutos.

## 1. Corrigir a maritimeco2 (5 min)

Sem isso, o `port-emissions-mcp` não instala.

```bash
git clone https://github.com/darlianecunha/maritimeco2
cd maritimeco2
```

No fim do `pyproject.toml`, acrescente:

```toml
[tool.setuptools]
packages = ["maritime_co2"]
```

Aproveite e corrija a linha `Homepage` para `https://github.com/darlianecunha/maritimeco2` (hoje aponta para `maritime-co2`, que não existe). O patch completo está em `docs/maritimeco2-fix.patch`.

```bash
pip install .        # deve terminar sem erro
git commit -am "Declare package for setuptools; fix homepage URL"
git push
```

## 2. Publicar o dataset no Zenodo (15 min)

Pasta pronta: `projetos/portos/zenodo-brazil-port-data/`.

1. **Confirme a licença da ANTAQ.** O seu README antigo dizia ODbL; no portal dados.gov.br a licença do conjunto não ficou clara. Se a fonte for ODbL ou domínio público, o pacote em ODbL está correto. Se encontrar outra licença, me avise antes de publicar.
2. Em zenodo.org, **New upload**, envie os 9 arquivos de `data/` mais `README.md`, `LICENSE.md` e `CITATION.cff`.
3. Preencha com os dados de `.zenodo.json` (título, descrição, palavras-chave, licença ODbL 1.0, ORCID). Ou, se preferir, publique pela integração GitHub do Zenodo com um repositório só de dados.
4. Publique. Anote o **número do registro** (o que aparece em zenodo.org/records/NÚMERO) e o **DOI**.

## 3. Ligar o MCP ao registro do Zenodo (5 min)

Me passe o número do registro e o DOI. Eu troco:
- `DEFAULT_RECORD` em `src/port_emissions_mcp/download.py`;
- os `XXXXXXX` do README do MCP e do README do dataset.

## 4. Publicar o MCP no GitHub (10 min)

```bash
cd projetos/portos/repositorios-github/port-emissions-mcp
git init && git add . && git commit -m "port-emissions-mcp 0.1.0"
gh repo create darlianecunha/port-emissions-mcp --public --source . --push
```

Confira antes do push: `git status` não deve listar nenhum CSV fora de `src/port_emissions_mcp/example_data/`.

## 5. Testar no Claude Desktop e gravar o GIF (15 min)

```bash
uv venv && uv pip install -e ".[test]"
uv run pytest
uv run port-emissions-mcp download
```

Em Claude Desktop, Configurações, Developer, Edit Config, cole o bloco do README com o caminho completo de `.venv/bin/port-emissions-mcp`. Reinicie o app. Use o prompt 6 de `docs/demo-prompts.md` e grave a tela (Cmd+Shift+5 no Mac). Salve como `docs/gallery/demo.gif` e descomente a linha do GIF no README.

## 6. Depois

- Adicionar o dataset e o MCP ao CV (seção "Selected AI projects") e ao ORCID (o Zenodo se conecta ao ORCID).
- Publicar o estudo de caso e o post do LinkedIn (projeto 5), que já citam este repositório.
