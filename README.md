# EHA Live

Visão de produção da Exception Handling Area, com **bips como indicador principal**, seleção de estação após o login e matriz de todos os SOCs por hora. Projeto independente do Cockpit, com a mesma prioridade de bips e abertura por motivo.

## O que está incluído

- Login corporativo Google e opção Login with SeaTalk.
- Escolha de estação ou de toda a rede ao entrar; preferência salva por conta.
- Cards de bips, pacotes, colaboradores por estação e hora de maior volume.
- Gráfico H/H com seleção de hora, ranking e motivos por colaborador.
- Matriz de todos os SOCs, mesmo quando uma estação está selecionada nos cards.
- Filtros por cutoff, SOC, fluxo e subárea; atualização da tela a cada minuto.
- Coletor autenticado de Google Sheets e histórico PostgreSQL com revisões imutáveis.
- Layout para computador e celular; marca vetorial em `static/brand/eha-live-logo.webp`.

O nome e a identidade são uma proposta inicial. Não são usados dados demonstrativos em produção. A aplicação começa vazia e aguarda a primeira coleta válida.

## Subir no Railway

Crie um projeto com **PostgreSQL e um serviço EHA ligado a este repositório**. Use o arquivo padrão 
ailway.toml, exponha uma URL pública e mantenha /healthz como healthcheck. O Dockerfile executa python start.py, que cria as tabelas e inicia o Web e o coletor no mesmo serviço. A coleta começa automaticamente e se repete a cada SYNC_SECONDS.

Cadastre todas as variáveis de Web e Coletor listadas abaixo no serviço EHA. Não é necessário criar um segundo serviço de aplicação. O supervisor encerra os dois processos e permite ao Railway reiniciar o serviço se um deles sair inesperadamente; os locks do banco impedem gravações simultâneas de coletores.

Se preferir separar os processos futuramente, use RUN_COLLECTOR=false no Web e crie o serviço Coletor com /railway.worker.toml e as variáveis da coleta. O coletor separado não precisa de domínio público nem healthcheck HTTP.

### Variáveis

| Variável | Serviço | Valor |
| --- | --- | --- |
| `DATABASE_URL` | Ambos | Referência `${{Postgres.DATABASE_URL}}`, ajustando o nome do serviço PostgreSQL |
| `APP_BASE_URL` | Web | URL HTTPS pública, sem barra final |
| `SECRET_KEY` | Web | Chave aleatória estável, com pelo menos 32 caracteres |
| `GOOGLE_CLIENT_ID` | Web | OAuth Client ID do tipo Web |
| `GOOGLE_CLIENT_SECRET` | Web | Segredo do mesmo cliente OAuth |
| `ALLOWED_GOOGLE_DOMAINS` | Web | Padrão: `shopee.com,shopeemobile-external.com` |
| `ALLOWED_EMAILS` | Web | Exceções explícitas, separadas por vírgula; opcional |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Coletor | JSON completo da conta de serviço, em uma variável secreta |
| `SPREADSHEET_ID` | Coletor | Padrão: `1swhGmEQhrn0tyMUrRHA0q6LaxWg4WFl9CnGJtM1Jg4w` |
| `SHEET_NAME` | Coletor | Padrão: `DB Resolved` |
| `SYNC_SECONDS` | Ambos | Padrão: `300`; mínimo de coleta: 60 segundos |
| `SEATALK_APP_ID` | Web | Opcional, para ativar Login with SeaTalk |
| `SEATALK_APP_SECRET` | Web | Opcional, segredo do aplicativo SeaTalk |

Gere a chave com `python -c "import secrets; print(secrets.token_hex(32))"`. Cadastre os segredos diretamente no Railway. Não envie `.env`, JSON de credenciais ou bases com nomes de colaboradores ao GitHub.

### Google: dois acessos diferentes

**Login das pessoas:** crie um cliente OAuth Web no Google Cloud. Configure o consentimento corporativo e adicione exatamente `https://SEU-DOMINIO/auth/callback` em Authorized redirect URIs. O login usa OpenID Connect; Authlib valida o token e o aplicativo exige identidade verificada e domínio corporativo (`hd`), ou uma exceção em `ALLOWED_EMAILS`.

**Leitura da base:** ative Google Sheets API, crie uma conta de serviço e compartilhe a planilha como **Leitor** com o `client_email` desse JSON. Salve o JSON em `GOOGLE_SERVICE_ACCOUNT_JSON` no coletor. O login de um usuário no painel não concede acesso à planilha para o coletor. O escopo da conta de serviço é somente leitura. Políticas corporativas podem exigir aprovação para esse compartilhamento.

### SeaTalk e área de trabalho

Cadastre um Workspace App com a URL HTTPS do Web como página de entrada e use `static/brand/eha-live-logo.webp` como referência da marca; exporte PNG caso o portal exija esse formato. Para a opção nativa de login, habilite Login with SeaTalk, configure o retorno `https://SEU-DOMINIO/auth/seatalk/callback` e cadastre o ID e segredo no serviço Web. O botão oficial e a troca de código seguem o contrato usado no Cockpit. O fluxo real depende da configuração do novo aplicativo no portal SeaTalk.

O acesso dos dois provedores é validado no servidor. A configuração inicial permite os domínios corporativos acima em todos os SOCs; seleção de estação é preferência de visualização, **não uma restrição de acesso**. Não há integração automática com o cadastro ou as permissões do banco do Cockpit.

## Contrato da base

A aba `DB Resolved`, intervalo `A:M`, deve manter estes cabeçalhos na linha 1 (a ordem pode mudar):

```text
year_resolved month_resolved week_resolved cutoff hora_resolucao soc_name
exception_reason operator fluxo resolved_shipment resolved_bips sub_area before_station_type
```

- `cutoff` é o **dia operacional já definido na fonte**, preservado sem deslocar a madrugada. Aceita data ISO, `dd/mm/aaaa` e serial de data nativo do Sheets.
- `hora_resolucao` é um inteiro de 0 a 23. O gráfico apresenta 00h–23h, sem inferir turnos.
- `resolved_bips` é o principal. `resolved_shipment` é secundário. Ambos são somas da base agregada, sem afirmar quantidade de remessas únicas entre linhas.
- Cada combinação cutoff + hora + SOC contém o conjunto completo das linhas daquela hora/estação. Dimensões iguais dentro da carga são somadas.
- Cabeçalhos obrigatórios ausentes/duplicados, contagem vazia, negativa ou fracionária, SOC vazio e data/hora inválida rejeitam a carga inteira. A última carga válida continua disponível.
- A ausência de registros é exibida como “—”. Um zero explícito é preservado como observação com valor zero.
- Operadores sem identificação aparecem como “Não informado”; a contagem é por identificador e SOC no recorte, sem deduplicação global de pessoas entre estações.

## Como o histórico funciona

O coletor consulta a fonte a cada cinco minutos por padrão. Um lock de sessão PostgreSQL impede coleta simultânea por duas réplicas. Ele normaliza e valida toda a resposta antes de gravar.

Para cada **cutoff + hora + SOC presente**, calcula um hash do conjunto agregado. Se o conteúdo mudou, cria uma revisão em `eha_revisions`, grava as linhas em `eha_facts` e atualiza a referência em `eha_latest`, tudo na mesma transação. Conteúdo idêntico apenas atualiza `last_seen_at`: **não acumula bips novamente**. As consultas somam apenas a revisão atual de cada hora/SOC.

Horas, SOCs ou dias ausentes de uma coleta seguinte mantêm a última observação; isso preserva histórico quando a planilha limpa dias anteriores. Uma hora/SOC reapresentada substitui integralmente seu conjunto de linhas, inclusive correções para baixo e remoção de operadores. As revisões anteriores permanecem no banco para auditoria técnica; esta primeira versão não oferece seletor de revisão no painel.

**Limite da fonte:** não é possível distinguir ausência por limpeza de histórico de uma exclusão intencional de toda uma hora/SOC. Para zerar uma hora já arquivada, a fonte precisa reapresentar esse SOC/hora com uma linha de contagem zero. Também não é possível recuperar dias que desapareceram antes da primeira coleta. Se a aba publica horas/SOCs de forma parcial durante atualização, programe o coletor após a atualização completa ou adicione um sinal de conclusão à fonte antes de operar continuamente.

As tabelas são independentes do Cockpit: `eha_runs` (status das coletas), `eha_revisions` (versões), `eha_facts` (contagens), `eha_latest` (última versão de cada hora/SOC) e `eha_preferences` (estação por conta). Não há expurgo automático de revisões nesta versão. Configure backups e acompanhe armazenamento no Railway.

O status da tela informa a última coleta bem-sucedida, falhas e atraso de coleta. Ele indica que a planilha foi lida, não garante que o processo que alimenta a planilha atualizou os dados. Em falhas, o painel mantém o histórico e exibe o aviso.

## Desenvolvimento e validação

Python 3.13. Instale `requirements.lock`, defina as variáveis de `.env.example` no ambiente e execute `python start.py` (Linux/Docker). Em outro serviço/processo execute `python worker.py`. Variáveis `.env` não são carregadas automaticamente. A autenticação exige URL HTTPS e cookies Secure; use um ambiente HTTPS de desenvolvimento para testar OAuth.

```bash
pip install -r requirements.lock
python -m unittest discover -s tests -v
python -m compileall -q .
node --check static/app.js
```

Os testes cobrem normalização, contagens, cutoff, ausência versus zero, segurança de sessão/CSRF, validação de filtros e matriz da rede. Os testes de rotas isolam o banco com fixtures. Para validar o armazenamento real, use um PostgreSQL de teste exclusivo e execute `python -m unittest discover -s tests -p test_postgres.py -v` com `TEST_DATABASE_URL` definido. Nunca aponte esse teste ao banco de produção.

O painel foi conferido em navegador com dados demonstrativos, incluindo seleção de SOC, hora, motivo, fluxo, estado vazio e versão móvel. A amostra enviada foi validada localmente sem inclusão no repositório. Login real, coleta autenticada, PostgreSQL do Railway e publicação SeaTalk precisam ser conferidos após configurar os serviços e credenciais.

## Referências oficiais

- [Railway: PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Railway: healthchecks](https://docs.railway.com/deployments/healthchecks)
- [Google: OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Google Sheets: leitura de valores](https://developers.google.com/workspace/sheets/api/guides/values)
- [Google: conta de serviço e compartilhamento](https://developers.google.com/workspace/guides/create-credentials)
- [SeaTalk: Workspace Apps e Login](https://seatalk.io/features/open)
