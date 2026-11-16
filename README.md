# EHA Live

Visão de produção da Exception Handling Area, com **bips como indicador principal**, seleção de estação após o login e matriz de todos os SOCs por hora. Projeto independente do Cockpit, com a mesma prioridade de bips e abertura por motivo.

## O que está incluído

- Visão geral para a opção Todos os SOCs. Ao escolher uma estação, a aba da rede fica oculta e o painel mostra somente aquele SOC. Use Trocar estação / visão para retornar à seleção.
- Visão geral dedicada à matriz de bips H/H de todos os SOCs, busca de estação e total da rede.
- Visão do SOC restrita à estação escolhida: indicadores, gráfico H/H, Pareto, motivos detalhados, fluxos e colaboradores.
- Pareto por `exception_reason`: barras de bips em ordem decrescente, linha de percentual acumulado e referência de 80%.
- Filtros por cutoff, estação (com digitação), fluxo, motivo da tratativa e hora. Sem subárea nas telas e filtros.
- Clique em uma hora para filtrar o detalhe; clique em um motivo do Pareto para abrir seu recorte.
- Horas preservadas no banco indicadas na estação. A janela de quatro horas da fonte não limita o histórico já coletado.
- Login por e-mail corporativo (Google) primeiro; Login with SeaTalk abaixo.
- Matriz H/H por operador e gráfico na sequência configurada para o SOC: primeira hora do T1 até a última hora do T3. Cutoff não é deslocado.
- Aba Configurações por unidade, com início de T1, T2 e T3, histórico de alteração, prevenção de sobrescrita concorrente e filtro de produção por turno.
- Coletor autenticado de Google Sheets, PostgreSQL com revisões imutáveis e preferência de estação por conta.
- Layout adaptável para computador e celular; marca Shopito em `static/brand/eha-live-logo.webp`.

Não são usados dados demonstrativos em produção. A aplicação começa vazia e aguarda a primeira coleta válida. O login SeaTalk e a visibilidade do Workspace são configurados no portal do aplicativo; o novo público e o One-Tap dependem de aprovação administrativa.

## Subir no Railway

Crie um projeto com **PostgreSQL e um serviço EHA ligado a este repositório**. Use o arquivo padrão `railway.toml`, exponha uma URL pública e mantenha /healthz como healthcheck. O Dockerfile executa python start.py, que cria as tabelas e inicia o Web e o coletor no mesmo serviço. A coleta começa automaticamente e se repete a cada SYNC_SECONDS.

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

## Configurações de turnos por unidade

Abra **Configurações**, escolha o SOC e informe o início de T1, T2 e T3. A base é agregada por hora, portanto são aceitas horas cheias. O fim de cada turno é o início do próximo; o T3 termina no início do T1, formando um ciclo contínuo de 24 horas sem sobreposição. A ordem dos inícios deve seguir T1 → T2 → T3 dentro desse ciclo.

O gráfico, a matriz por operador e a faixa de horas preservadas começam no início do T1 e terminam uma hora antes do seu reinício, após o T3. Exemplos: T1 às 07h resulta em 07h–06h; T1 às 06h resulta em 06h–05h. A configuração de uma unidade não modifica outra.

Sem configuração salva, a ordem da visão individual é 06h D0–05h D+1 para todos os SOCs, exceto SoC_RJ_Jacarepagua (07h D0–06h D+1). Configuração salva tem prioridade. Os turnos não são presumidos. T2 e T3 ficam em branco no formulário até o usuário informar os horários reais. Não há associação automática entre siglas RJ1/RJ4 e nomes de SOC.

Na Produção, use Dia completo/T1/T2/T3 para filtrar indicadores, Pareto e operadores. O gráfico mantém as 24 horas ordenadas e atenua os outros turnos. A configuração é compartilhada entre as contas autorizadas e aplicada aos dias consultados; as datas, horas e contagens armazenadas não são regravadas. O cutoff bruto da fonte é preservado com corte às 06h. A consulta reconstrói a data civil (cutoff + 1 dia para 00h–05h) e aplica o início do T1 da unidade. Assim, as 06h que fecham o ciclo 07h–06h vêm do cutoff seguinte, nunca das 06h de D0. A consulta usa a mesma regra para indicadores, gráfico, operadores, motivos e cobertura. A visão geral sempre usa o ciclo comum 06h D0–05h D+1 para todas as unidades, independentemente das configurações individuais.

Os horários são persistidos em `eha_unit_settings`, com versão e conta responsável. Cada gravação gera auditoria em `eha_unit_settings_audit`. O formulário impede que uma versão antiga sobrescreva silenciosamente uma alteração mais recente. As tabelas são criadas automaticamente na inicialização do serviço.

## Contrato da base

A aba `DB Resolved`, intervalo `A:M`, usa estes cabeçalhos na linha 1 (a ordem pode mudar; sub_area é opcional e ignorada na interface):

```text
year_resolved month_resolved week_resolved cutoff hora_resolucao soc_name
exception_reason operator fluxo resolved_shipment resolved_bips sub_area before_station_type
```

- `cutoff` é o **dia operacional da fonte com corte às 06h**, preservado no armazenamento. A visão individual ajusta a consulta à jornada da unidade, sem regravar as coletas. Aceita data ISO, `dd/mm/aaaa` e serial de data nativo do Sheets.
- `hora_resolucao` é um inteiro de 0 a 23. A rede apresenta 06h D0–05h D+1; o detalhe apresenta o ciclo da unidade, com indicação D0/D+1.
- `resolved_bips` é o principal. `resolved_shipment` é secundário. Ambos são somas da base agregada, sem afirmar quantidade de remessas únicas entre linhas.
- Cada combinação cutoff + hora + SOC contém o conjunto completo das linhas daquela hora/estação. Dimensões iguais dentro da carga são somadas.
- Cabeçalhos obrigatórios ausentes/duplicados, contagem vazia, negativa ou fracionária, SOC vazio e data/hora inválida rejeitam a carga inteira. A última carga válida continua disponível.
- A ausência de registros é exibida como “—”. Um zero explícito é preservado como observação com valor zero.
- A coluna `sub_area`, se existir na fonte, é metadado opcional de armazenamento e não é usada como motivo da tratativa nem exibida no produto. `exception_reason` é a única origem dos motivos.

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

A versão inicial foi conferida em navegador com dados demonstrativos. A revisão com abas independentes, Pareto e busca digitável foi verificada por testes de contrato, renderização de templates e sintaxe; a conferência visual da primeira revisão ficou pendente por limite de uso. Após a liberação, a revisão com matriz H/H por operador, busca de estação, isolamento do SOC e ordem dos botões de login foi conferida em navegador com dados demonstrativos. A amostra enviada foi validada localmente sem inclusão no repositório. Login real, coleta autenticada, PostgreSQL do Railway e publicação SeaTalk precisam ser conferidos após configurar os serviços e credenciais.

## Referências oficiais

- [Railway: PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Railway: healthchecks](https://docs.railway.com/deployments/healthchecks)
- [Google: OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Google Sheets: leitura de valores](https://developers.google.com/workspace/sheets/api/guides/values)
- [Google: conta de serviço e compartilhamento](https://developers.google.com/workspace/guides/create-credentials)
- [SeaTalk: Workspace Apps e Login](https://seatalk.io/features/open)
