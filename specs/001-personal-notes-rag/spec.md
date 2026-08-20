# Feature Specification: Gerenciamento de Anotações Pessoais com RAG

**Feature Branch**: `N/A (branch hook not configured)`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "Aplicação de gerenciamento de anotações pessoais com autenticação,
isolamento entre usuários e interação por chatbot com RAG local, no qual a recuperação semântica é um
mecanismo interno das consultas às anotações."

## Revision History

- **2026-08-19 — Revisão controlada pós-implementação**: Uma verificação de equivalência funcional
  realizada após a primeira implementação e validação do experimento identificou que a capacidade de
  conversa geral já existente na aplicação de referência não havia sido registrada na
  Especificação-Base. Esta revisão restaura essa equivalência nos artefatos experimentais; não introduz
  uma melhoria funcional nova e não reclassifica resultados da primeira implementação.
- **2026-08-20 — Revisão controlada pós-implementação**: A validação funcional posterior identificou a
  necessidade de explicitar o modelo de linguagem local como classificador primário de toda mensagem e
  de retirar a busca semântica do conjunto de funcionalidades independentes do usuário, preservando-a
  exclusivamente como mecanismo interno do RAG. O registro histórico anterior é mantido, e esta revisão
  substitui somente as regras de roteamento e de exposição da recuperação semântica afetadas.

## Clarifications

### Session 2026-08-17

- Q: Qual identificador único o usuário deverá utilizar para cadastro e autenticação? → A: Nome de
  usuário único.
- Q: Quais informações devem compor uma anotação criada ou editada pelo usuário? → A: Título e
  conteúdo obrigatórios.
- Q: O que deverá acontecer quando o usuário confirmar a exclusão de uma anotação? → A: Excluir
  permanentemente após confirmação.
- Q: Quando uma anotação for criada ou atualizada, em quanto tempo ela deverá ficar disponível para
  recuperação semântica interna e respostas do chatbot? → A: Em até 30 segundos, indicando preparação.
- Q: Qual credencial o usuário deverá fornecer junto ao nome de usuário para se autenticar? → A: Senha
  definida pelo usuário.

### Session 2026-08-19

- Q: Qual regra funcional deve determinar se uma mensagem clara é consulta às anotações ou conversa
  geral? → A: A intenção expressa na própria mensagem determina o modo: referências ao que o usuário
  anotou, registrou ou possui em suas notas indicam RAG; perguntas independentes das notas indicam
  conversa geral; a existência de notas semanticamente semelhantes não altera essa intenção. **Registro
  histórico substituído em 2026-08-20 pela exigência de classificação semântica primária pelo modelo de
  linguagem local; os exemplos linguísticos não constituem regras determinísticas de roteamento.**
- Q: Como a interface deve distinguir visualmente uma resposta geral de uma resposta fundamentada nas
  anotações? → A: Exibir indicadores explícitos nos dois modos, “Resposta geral” e “Baseada nas suas
  anotações”, mantendo fontes somente no modo RAG.
- Q: O que o chatbot deve fazer quando uma única mensagem combina claramente duas ou mais intenções,
  como conversa geral, consulta às anotações e criação? → A: Solicitar que o usuário escolha uma única
  intenção; antes do esclarecimento, não responder à pergunta nem criar anotação.

### Session 2026-08-20

- Q: Quando a classificação não puder produzir uma intenção válida, o chatbot deve solicitar
  esclarecimento ou apresentar um erro sem executar nenhuma ação? → A: A intenção válida
  `clarification` solicita esclarecimento; falha técnica, saída inválida ou fora do schema apresenta
  erro acionável sem executar ação.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gerenciar anotações pessoais com segurança (Priority: P1)

Como usuário, quero criar uma conta, autenticar-me e gerenciar minhas próprias anotações para manter
informações pessoais disponíveis e protegidas ao longo do tempo.

**Why this priority**: Cadastro, autenticação, isolamento e gerenciamento de anotações formam a base
de valor e segurança sobre a qual todas as capacidades de recuperação são construídas.

**Independent Test**: Pode ser testada com dois usuários cadastrados, cada qual criando, listando,
consultando, atualizando e excluindo suas próprias anotações, inclusive após reinicialização, sem que
um consiga acessar dados do outro.

**Acceptance Scenarios**:

1. **Given** que não existe conta com determinado nome de usuário, **When** uma pessoa fornece esse nome
   e uma senha válida definida por ela, **Then** o sistema cria uma conta única e confirma o cadastro.
2. **Given** que já existe uma conta com o nome de usuário informado, **When** outra tentativa de
   cadastro usa o mesmo nome, **Then** o sistema rejeita o conflito sem criar uma duplicata.
3. **Given** uma conta existente, **When** o usuário fornece seu nome de usuário e senha válidos,
   **Then** o sistema o autentica e concede acesso às funcionalidades relacionadas às suas informações
   pessoais.
4. **Given** nome de usuário ou senha inválidos, ou ausência de autenticação, **When** alguém tenta
   acessar uma funcionalidade protegida, **Then** o sistema nega o acesso sem revelar qual credencial
   falhou, dados pessoais ou detalhes internos sensíveis.
5. **Given** um usuário autenticado, **When** ele cria uma anotação com título e conteúdo válidos,
   **Then** a anotação é persistida, associada somente a ele e fica disponível para consulta e
   listagem.
6. **Given** anotações pertencentes a dois usuários, **When** cada usuário lista ou consulta suas
   anotações, **Then** recebe exclusivamente as anotações que lhe pertencem.
7. **Given** uma anotação própria existente, **When** o usuário altera seu título ou conteúdo mantendo
   ambos válidos, **Then** o sistema persiste a versão atualizada e a apresenta nas consultas
   posteriores.
8. **Given** uma anotação própria existente, **When** o usuário confirma sua exclusão, **Then** ela e
   suas representações recuperáveis são removidas permanentemente, sem possibilidade de restauração,
   e deixam de aparecer em consultas, listagens, recuperações semânticas e respostas futuras.
9. **Given** usuários e anotações persistidos, **When** a aplicação é reiniciada e o usuário volta a
   autenticar-se, **Then** seus dados continuam disponíveis e associados corretamente.

---

### User Story 3 - Consultar anotações pelo chatbot (Priority: P3)

Como usuário autenticado, quero fazer perguntas em linguagem natural e receber respostas baseadas nas
minhas anotações, identificando as fontes utilizadas, para consultar meu conhecimento pessoal com
confiança.

**Why this priority**: Esta história entrega o fluxo RAG completo sobre a base segura de gerenciamento,
usando recuperação semântica somente como mecanismo interno de seleção de contexto.

**Independent Test**: Pode ser testada com um conjunto controlado de anotações, perguntas cujas
respostas estejam ou não no corpus e verificação das fontes apresentadas e do isolamento por usuário.

**Acceptance Scenarios**:

1. **Given** anotações próprias relevantes, **When** o modelo de linguagem local classifica uma mensagem
   como `rag` e o resultado é validado, **Then** o sistema realiza retrieval semântico interno apenas
   sobre suas anotações, usa o contexto autorizado e produz uma resposta fundamentada nesse contexto.
2. **Given** que uma resposta utiliza anotações recuperadas, **When** a resposta é apresentada,
   **Then** ela é identificada como “Baseada nas suas anotações” e o usuário consegue identificar quais
   de suas anotações foram usadas como fontes, sem ser obrigado a visualizar um score numérico de
   relevância.
3. **Given** que as anotações próprias não oferecem base suficiente, **When** o usuário faz uma
   pergunta, **Then** o sistema comunica a insuficiência de contexto em vez de apresentar como fato uma
   resposta não sustentada pelas anotações.
4. **Given** anotações relevantes pertencentes somente a outro usuário, **When** o usuário autenticado
   faz uma pergunta relacionada, **Then** a resposta não contém, não referencia e não é influenciada
   pelo conteúdo alheio.
5. **Given** uma sessão de uso normal, **When** o usuário interage com o chatbot, **Then** perguntas e
   respostas são apresentadas em uma interface conversacional compreensível.

---

### User Story 6 - Fazer perguntas gerais ao chatbot (Priority: P3)

Como usuário autenticado, quero fazer perguntas gerais que não dependam das minhas anotações e receber
respostas do modelo de linguagem local para usar o chatbot também fora da consulta ao meu conhecimento
pessoal.

**Why this priority**: Restaura uma capacidade presente na aplicação de referência e completa a
equivalência funcional do chatbot sem enfraquecer o grounding das consultas dirigidas às anotações.

**Independent Test**: Pode ser testada com um dataset controlado contendo “O que é Docker?”, “Qual é a
capital do Peru?”, “Onde fica Machu Picchu?” e “Por que o céu é azul?”, verificando que todas passam
primeiro pelo mesmo classificador primário `llama3:latest` e resultam em `general_chat`, com ou sem
anotações semanticamente semelhantes, sem fontes e sem mensagem de contexto insuficiente. Esse resultado
esperado é um critério de aceitação do dataset, não uma regra de correspondência textual.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado, **When** ele envia uma pergunta geral que não depende de suas
   anotações, **Then** o modelo de linguagem local a classifica primariamente, o resultado `general_chat`
   é validado e somente então o chatbot responde usando o conhecimento geral desse modelo.
2. **Given** uma pergunta geral e nenhuma anotação semanticamente relevante, **When** o chatbot
   responde, **Then** a ausência de anotações não impede a resposta nem produz, por si só, uma mensagem
   de contexto insuficiente.
3. **Given** uma pergunta geral e uma ou mais anotações semanticamente semelhantes, **When** a mensagem
   não indica intenção de consultar o que foi anotado, **Then** o chatbot mantém a conversa geral e não
   transforma a mensagem em consulta às anotações por causa dos resultados recuperáveis.
4. **Given** uma resposta de conversa geral que não utilizou anotações, **When** ela é apresentada,
   **Then** ela é identificada como “Resposta geral”, nenhuma anotação é exibida ou atribuída como fonte
   e a resposta não é apresentada como fundamentada no corpus do usuário.
5. **Given** uma pergunta explicitamente dirigida às anotações do usuário, mas sem contexto suficiente
   no corpus, **When** o chatbot processa a consulta, **Then** informa a insuficiência de contexto e não
   a substitui silenciosamente por uma resposta de conhecimento geral.
6. **Given** indisponibilidade de APIs externas de modelo de linguagem, **When** o usuário faz uma
   pergunta geral, **Then** a geração continua disponível por meio do modelo executado localmente.
7. **Given** uma mensagem que combina claramente duas ou mais intenções entre criação, consulta às
   anotações e conversa geral, **When** o modelo de linguagem local a classifica como `clarification` e
   o resultado é validado, **Then** o chatbot solicita que o usuário escolha uma única intenção e não
   responde à pergunta nem cria anotação antes do esclarecimento.
8. **Given** o dataset controlado com as perguntas “O que é Docker?”, “Qual é a capital do Peru?”, “Onde
   fica Machu Picchu?” e “Por que o céu é azul?”, **When** cada mensagem passa primeiro pelo mesmo
   classificador primário `llama3:latest`, **Then** todas resultam em `general_chat`; esse resultado é o
   oráculo semântico do dataset e não pode ser decidido diretamente por regex, palavra-chave, prefixo ou
   estrutura linguística.
9. **Given** as consultas “O que eu anotei sobre Docker?” e “Segundo minhas anotações, qual era o horário
   da reunião?”, **When** cada mensagem é classificada, **Then** o mesmo classificador local pode produzir
   `rag`, antes de qualquer retrieval.

---

### User Story 4 - Criar anotação por conversa (Priority: P4)

Como usuário autenticado, quero pedir em linguagem natural que o chatbot crie uma anotação para
registrar informações sem sair da conversa.

**Why this priority**: Acrescenta conveniência à criação já disponível, mas depende da interpretação
segura da intenção e não é necessária para consultar o corpus existente.

**Independent Test**: Pode ser testada enviando pedidos claros e ambíguos ao chatbot e verificando a
interpretação, persistência, confirmação e associação exclusiva ao usuário autenticado.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado, **When** ele solicita claramente a criação de uma anotação e
   fornece título e conteúdo válidos, **Then** o modelo de linguagem local classifica primariamente a
   mensagem, o resultado `create_note` é validado e somente então o sistema cria e persiste a anotação
   em seu nome e apresenta uma confirmação com conteúdo identificável.
2. **Given** uma solicitação sem título ou sem conteúdo válido, **When** o sistema a interpreta,
   **Then** solicita a informação ausente e não cria uma anotação incompleta.
3. **Given** uma mensagem que é apenas uma pergunta, **When** o chatbot a interpreta, **Then** não cria
   uma anotação inadvertidamente.
4. **Given** uma anotação criada pelo chatbot, **When** o usuário a consulta pela funcionalidade de
   gerenciamento após reiniciar a aplicação, **Then** ela permanece disponível como qualquer outra
   anotação própria.

---

### User Story 5 - Executar o fluxo principal de forma reproduzível (Priority: P5)

Como responsável pela execução da aplicação, quero iniciar de forma reproduzível os componentes
necessários para o fluxo principal, incluindo geração local, para que cadastro, anotações e chatbot
funcionem sem dependência obrigatória de uma API externa de modelo de linguagem.

**Why this priority**: Garante portabilidade e autonomia operacional da solução completa, depois que
os comportamentos de usuário estiverem especificados.

**Independent Test**: Pode ser testada em um ambiente compatível e limpo, seguindo apenas a
configuração e instruções fornecidas para iniciar a solução, executar o fluxo principal e reiniciá-la.

**Acceptance Scenarios**:

1. **Given** um ambiente limpo com os pré-requisitos documentados, **When** o responsável segue as
   instruções de execução containerizada, **Then** todos os componentes necessários ao fluxo principal
   ficam disponíveis de forma reproduzível.
2. **Given** indisponibilidade de APIs externas de modelo de linguagem, **When** o usuário realiza o
   fluxo principal do chatbot, **Then** a geração de respostas continua disponível por meio de um
   modelo executado localmente.
3. **Given** dados persistidos durante uma execução, **When** os componentes são interrompidos e
   iniciados novamente conforme as instruções, **Then** usuários e anotações permanecem disponíveis.

### Edge Cases

- Cadastro com nome de usuário vazio, malformado ou equivalente a outro nome segundo as regras de
  unicidade deve ser rejeitado sem criar conta parcial.
- Cadastro com senha vazia ou inválida segundo as regras informadas ao usuário deve ser rejeitado sem
  criar conta parcial nem registrar a senha em texto simples.
- Tentativas repetidas com credenciais inválidas devem continuar sem revelar se dados pessoais existem
  nem expor credenciais ou detalhes internos.
- Consulta, alteração ou exclusão de uma anotação inexistente ou pertencente a outro usuário deve
  produzir resposta indistinguível quanto à existência de dados alheios.
- Uma solicitação de exclusão sem confirmação não deve remover nem alterar a anotação.
- Criação ou atualização com título ou conteúdo vazio deve ser rejeitada com orientação compreensível.
- Uma atualização deve invalidar o conteúdo anterior para retrieval interno; uma exclusão deve impedir
  que conteúdo residual apareça no contexto, nas respostas ou nas fontes.
- Falha temporária na preparação semântica deve ser informada sem perder a anotação persistida; o
  sistema deve permitir que a preparação seja retomada e não deve apresentar a versão anterior como
  se fosse o conteúdo atual.
- Consultas vazias ou resultados de classificação inválidos devem falhar de modo fechado, receber
  orientação e não iniciar retrieval, geração geral, criação ou qualquer outra ação.
- Uma pergunta geral não deve ser recusada apenas porque não existem anotações semanticamente
  relevantes, e uma resposta geral não deve exibir fontes de anotações que não foram utilizadas.
- A existência de anotações semanticamente semelhantes não deve transformar uma pergunta geral em
  consulta às anotações; retrieval e seus resultados ocorrem somente depois de classificação `rag`
  validada e nunca determinam a intenção.
- Uma consulta explicitamente dirigida às anotações sem contexto suficiente deve informar a
  insuficiência, mesmo que o modelo possua conhecimento geral sobre o tema.
- Quando não for possível distinguir com segurança entre consulta às anotações e conversa geral, o
  chatbot deve solicitar esclarecimento em vez de atribuir silenciosamente a mensagem ao modo errado.
- Mensagens que combinem claramente duas ou mais intenções entre criação, consulta às anotações e
  conversa geral devem solicitar que o usuário escolha uma única intenção; antes do esclarecimento, o
  chatbot não deve responder à pergunta nem criar anotação.
- Regex, palavras-chave, prefixos, formato interrogativo ou outras heurísticas não devem decidir
  diretamente a intenção nem substituir a classificação semântica primária do modelo de linguagem
  local; regras determinísticas limitam-se a normalização, validação de schema, segurança e fail-closed.
- Uma intenção válida `clarification` deve solicitar esclarecimento ao usuário sem executar retrieval,
  resposta geral, criação ou outra ação. Falha técnica, saída inválida, fora do schema ou com intenção
  não permitida deve apresentar erro acionável e falhar de modo fechado, também sem executar ação.
- Uma resposta com várias fontes deve permitir distinguir cada anotação utilizada; fontes excluídas ou
  de outro usuário nunca devem ser exibidas.
- Conteúdo de anotação que contenha instruções deve ser tratado como dado do usuário e não deve alterar
  as regras de isolamento, autorização ou comportamento do sistema.
- Indisponibilidade da geração local deve resultar em erro previsível e acionável, sem comprometer os
  dados persistidos ou recorrer silenciosamente a uma API externa.
- Reinicialização durante criação, atualização ou exclusão não deve produzir duplicação nem expor um
  estado parcialmente confirmado como concluído.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir o cadastro com um nome de usuário obrigatório e único, usado
  também para autenticação.
- **FR-002**: O sistema DEVE rejeitar cadastros com nomes de usuário conflitantes ou duplicados sem
  criar contas adicionais.
- **FR-003**: O sistema DEVE permitir que usuários cadastrados se autentiquem mediante nome de usuário
  e senha definida no cadastro e DEVE negar funcionalidades protegidas quando a autenticação estiver
  ausente ou inválida.
- **FR-004**: O sistema NÃO DEVE armazenar senhas em texto simples nem expor senhas, informações
  sensíveis, a credencial específica que falhou ou detalhes internos em mensagens, logs ou respostas.
- **FR-005**: O sistema DEVE associar cada anotação exatamente ao usuário que a criou.
- **FR-006**: Cada anotação DEVE possuir título e conteúdo obrigatórios, e o sistema DEVE permitir que
  um usuário autenticado crie, liste, consulte, atualize e exclua exclusivamente suas próprias
  anotações.
- **FR-007**: O sistema DEVE impedir que uma anotação seja consultada, recuperada, alterada, excluída,
  usada como contexto ou citada como fonte para qualquer usuário diferente de seu proprietário.
- **FR-008**: O sistema DEVE persistir usuários e anotações para que permaneçam disponíveis após
  reinicializações da aplicação.
- **FR-009**: O sistema DEVE persistir imediatamente criações e atualizações, que DEVEM disparar o ciclo
  assíncrono de indexação das notas, incluindo geração de embeddings, persistência vetorial e atualização
  do índice, independentemente de mensagens ou intenções do chatbot. O sistema DEVE indicar quando essa
  preparação interna estiver em andamento e disponibilizar o conteúdo atual ao retrieval interno do RAG
  em até 30 segundos, refletindo também atualizações e exclusões; esse mecanismo NÃO DEVE ser exposto
  como tela, menu, fluxo dedicado ou funcionalidade independente de busca para o usuário.
- **FR-010**: Depois de uma mensagem ser classificada como `rag` e o resultado ser validado, o sistema
  DEVE executar internamente a recuperação vetorial por relevância semântica, sem depender exclusivamente
  de correspondência textual exata, selecionar somente o contexto autorizado pertencente ao usuário
  autenticado, fundamentar a resposta nesse contexto e apresentar as fontes efetivamente utilizadas;
  NÃO DEVE existir endpoint público exclusivo nem operação independente de busca semântica voltada ao
  usuário.
- **FR-011**: O corpus disponível à recuperação e à geração fundamentada em anotações DEVE conter
  exclusivamente anotações cadastradas na aplicação; essa restrição de corpus não impede a geração
  separada de respostas de conversa geral que não utilizem anotações.
- **FR-012**: O sistema DEVE oferecer uma interface conversacional na qual o usuário autenticado possa
  enviar perguntas e visualizar respostas em linguagem natural.
- **FR-013**: Para cada mensagem com classificação `rag` validada, o sistema DEVE recuperar internamente
  anotações semanticamente relevantes pertencentes exclusivamente ao usuário autenticado, selecionar o
  contexto autorizado e usá-lo na resposta grounded com fontes.
- **FR-014**: Quando uma consulta dirigida às anotações não possuir contexto recuperado suficiente, o
  sistema DEVE indicar a insuficiência sem preencher lacunas com conhecimento geral, sem atribuir às
  anotações informações que elas não contenham e sem converter silenciosamente a consulta em conversa
  geral.
- **FR-015**: Quando uma resposta usar anotações como contexto, o sistema DEVE permitir que o usuário
  identifique o modo como “Baseada nas suas anotações” e cada anotação utilizada como fonte; a exibição
  de score numérico de relevância é opcional.
- **FR-016**: O chatbot DEVE reconhecer solicitações explícitas de criação de anotação em linguagem
  natural, obter esclarecimento quando faltar conteúdo essencial e evitar criação quando a intenção
  não estiver suficientemente clara.
- **FR-017**: Após reconhecer uma solicitação válida de criação, o sistema DEVE criar e persistir a
  anotação para o usuário autenticado e fornecer uma confirmação identificável.
- **FR-018**: O sistema DEVE fornecer configuração e instruções de containerização suficientes para
  executar de modo reproduzível os componentes necessários ao fluxo principal.
- **FR-019**: `llama3:latest` DEVE ser o único modelo de linguagem generativo e classificador do fluxo
  principal, executado localmente, e a geração ou classificação NÃO DEVE depender de uma API externa de
  modelo de linguagem nem introduzir um segundo LLM.
- **FR-020**: Falhas DEVEM resultar em comportamento previsível e mensagens compreensíveis, sem expor
  dados de outros usuários, informações sensíveis ou detalhes internos.
- **FR-021**: Após confirmação do usuário, o sistema DEVE excluir permanentemente a anotação e todas as
  suas representações recuperáveis, sem oferecer restauração ou lixeira.
- **FR-022**: Toda mensagem conversacional DEVE passar primeiro por `llama3:latest` como classificador
  semântico primário, produzindo exatamente uma intenção entre `rag`, `general_chat`, `create_note` e
  `clarification`; o resultado DEVE ser validado antes do roteamento e antes de retrieval, resposta
  geral, criação ou qualquer outra ação. Regex, palavras-chave, prefixos, estrutura linguística ou
  outras heurísticas NÃO DEVEM decidir diretamente a intenção nem substituir a classificação do modelo.
  Regras determinísticas são permitidas somente para normalização, validação de schema, segurança e
  comportamento fail-closed. Resultados de retrieval semântico NÃO DEVEM determinar nem alterar a
  intenção, pois retrieval somente pode ocorrer após uma classificação `rag` validada. Uma intenção
  válida `clarification` DEVE solicitar esclarecimento sem executar ação. Falha técnica ou resultado
  inválido, fora do schema, com intenção não permitida ou inseguro DEVE apresentar erro acionável e
  falhar de modo fechado, sem executar ação.
- **FR-023**: Após uma classificação `general_chat` validada, quando a resposta não utilizar anotações,
  o sistema NÃO DEVE exibir
  nem atribuir anotações como fontes e NÃO DEVE apresentar a resposta como fundamentada no corpus do
  usuário; a interface DEVE identificar explicitamente o modo como “Resposta geral”.

### Key Entities *(include if feature involves data)*

- **Usuário**: Pessoa que possui um nome de usuário único, uma senha definida por ela e protegida pelo
  sistema e acesso autenticado; é proprietária de zero ou mais anotações.
- **Anotação**: Informação pessoal pertencente a exatamente um usuário, com identidade própria, título
  obrigatório, conteúdo obrigatório e estado atual decorrente de criação ou alteração; deixa de
  existir definitivamente após exclusão confirmada.
- **Representação recuperável**: Forma conceitual derivada do conteúdo atual de uma anotação que
  permite compará-la semanticamente com uma consulta; mantém vínculo inequívoco com a anotação e seu
  proprietário e deixa de ser utilizável após atualização substitutiva ou exclusão.
- **Consulta conversacional**: Pergunta ou solicitação em linguagem natural feita por um usuário
  autenticado, classificada primariamente pelo modelo de linguagem local como `rag`, `general_chat`,
  `create_note` ou `clarification` antes do roteamento e de qualquer ação.
- **Resposta conversacional**: Resultado apresentado ao usuário; em consulta às anotações, é
  fundamentado no corpus permitido e acompanhado das fontes utilizadas; em conversa geral, utiliza o
  conhecimento do modelo local sem atribuir fontes de anotações não utilizadas.
- **Fonte**: Referência identificável a uma anotação própria efetivamente utilizada como contexto de
  uma resposta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em testes de aceitação, 100% das tentativas de acesso cruzado entre usuários são negadas
  e nenhum conteúdo alheio aparece em listagens, contextos recuperados, respostas ou fontes.
- **SC-002**: Usuários concluem cadastro, autenticação e criação da primeira anotação em até 3 minutos
  em pelo menos 90% dos testes moderados, sem assistência técnica.
- **SC-003**: Todas as cinco operações de gerenciamento preservam o estado esperado após reinicialização
  em 100% dos cenários de persistência definidos.
- **SC-004**: Em um conjunto de mensagens classificadas e validadas como `rag`, com consultas
  semanticamente equivalentes sem palavras-chave idênticas, pelo menos 85% incluem entre os cinco itens
  de contexto selecionados internamente uma anotação própria julgada relevante pelo conjunto de teste,
  sem expor uma funcionalidade independente de busca ao usuário.
- **SC-005**: Pelo menos 90% das perguntas respondíveis no conjunto de aceitação recebem resposta
  compatível com o conteúdo das anotações fornecidas, sem afirmações contraditórias às fontes.
- **SC-006**: Em 100% das respostas que utilizam contexto recuperado, todas as anotações efetivamente
  usadas são identificáveis como fontes e nenhuma fonte não utilizada ou alheia é apresentada.
- **SC-007**: Pelo menos 90% dos usuários de teste conseguem fazer uma pergunta e localizar suas fontes
  na interface conversacional na primeira tentativa.
- **SC-008**: Pelo menos 95% das solicitações claras de criação via chatbot geram exatamente uma
  anotação com o conteúdo pretendido e uma confirmação compreensível; solicitações ambíguas não geram
  anotação sem esclarecimento.
- **SC-009**: Em ambiente limpo compatível, com os pré-requisitos, imagens e modelos documentados já
  disponíveis, um responsável consegue iniciar o fluxo principal seguindo apenas as instruções
  fornecidas em até 15 minutos e obtém o mesmo conjunto de capacidades em três execuções consecutivas.
  O tempo necessário para downloads iniciais deve ser registrado separadamente e não integra essa
  medição.
- **SC-010**: O conjunto completo de aceitação do fluxo principal funciona com APIs externas de modelo
  de linguagem indisponíveis, usando geração executada localmente.
- **SC-011**: Em pelo menos 95% das criações e atualizações do conjunto de aceitação, a versão atual da
  anotação fica disponível ao retrieval interno do RAG e às respostas em até 30 segundos; durante o
  intervalo, o estado de preparação é visível ao usuário.
- **SC-012**: Em 100% das mensagens conversacionais do conjunto de aceitação, `llama3:latest` atua como
  classificador semântico primário antes de retrieval, resposta geral, criação ou qualquer ação, e o
  roteamento ocorre somente após validação de uma intenção `rag`, `general_chat`, `create_note` ou
  `clarification`. Em 100% das perguntas gerais claras, inclusive nos quatro formatos linguísticos
  exemplificados em US6, a ausência ou presença de anotações semanticamente semelhantes não determina
  a intenção nem causa, por si só, recusa por contexto insuficiente; respostas que não utilizam
  anotações são identificadas como “Resposta geral” e apresentadas sem fontes, enquanto respostas RAG
  são grounded, identificadas como “Baseada nas suas anotações” e acompanhadas de fontes.

## Assumptions

- Há um único tipo de usuário final; funções administrativas e compartilhamento de anotações não fazem
  parte desta feature.
- O nome de usuário é fornecido pela pessoa no cadastro e possui uma regra de equivalência consistente,
  documentada ao usuário, para detectar conflitos de caixa, espaços ou outras variações aplicáveis.
- Recuperação semântica é exclusivamente um mecanismo interno do RAG e pode selecionar nenhuma, uma ou
  várias anotações, conforme relevância suficiente; embeddings, indexação, armazenamento e recuperação
  vetorial, isolamento por usuário, seleção de contexto, grounding e fontes permanecem preservados. Não
  existe tela, menu, fluxo dedicado, endpoint público exclusivo ou obrigação de exibir score numérico.
- Respostas a consultas dirigidas às anotações devem se limitar ao que pode ser sustentado pelo corpus
  do usuário e não podem preencher lacunas com conhecimento geral. Respostas a perguntas gerais podem
  utilizar o conhecimento do modelo de linguagem local, desde que não sejam apresentadas como
  provenientes das anotações nem exibam fontes de anotações não utilizadas. Toda mensagem é classificada
  primariamente por `llama3:latest`; a existência ou relevância de anotações, palavras-chave, regex,
  prefixos ou estrutura linguística não determina diretamente o modo conversacional.
- `llama3:latest` permanece como único modelo de linguagem generativo e classificador. A classificação
  precede retrieval, resposta geral, criação e qualquer ação; regras determinísticas limitam-se a
  normalização, validação de schema, segurança e fail-closed.
- A criação via chatbot exige título e conteúdo válidos, mas não exige que o usuário use um comando
  rígido ou uma frase específica.
- A configuração containerizada e a execução local destinam-se ao fluxo principal em ambiente
  compatível; quantidade de componentes, topologia e demais decisões são reservadas ao planejamento.
- Uploads, anexos, PDFs, DOCX, ingestão e RAG sobre documentos externos permanecem fora do escopo.
- Recuperação de credenciais, colaboração entre usuários, compartilhamento, versionamento de anotações
  e importação ou exportação não são introduzidos por esta specification. Lixeira, arquivamento e
  restauração de anotações também permanecem fora do escopo.
