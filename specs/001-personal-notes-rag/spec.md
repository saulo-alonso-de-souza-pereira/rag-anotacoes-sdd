# Feature Specification: Gerenciamento de Anotações Pessoais com RAG

**Feature Branch**: `N/A (branch hook not configured)`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "Aplicação de gerenciamento de anotações pessoais com autenticação,
isolamento entre usuários, recuperação semântica e interação por chatbot com RAG local."

## Clarifications

### Session 2026-08-17

- Q: Qual identificador único o usuário deverá utilizar para cadastro e autenticação? → A: Nome de
  usuário único.
- Q: Quais informações devem compor uma anotação criada ou editada pelo usuário? → A: Título e
  conteúdo obrigatórios.
- Q: O que deverá acontecer quando o usuário confirmar a exclusão de uma anotação? → A: Excluir
  permanentemente após confirmação.
- Q: Quando uma anotação for criada ou atualizada, em quanto tempo ela deverá ficar disponível para
  busca semântica e respostas do chatbot? → A: Em até 30 segundos, indicando preparação.
- Q: Qual credencial o usuário deverá fornecer junto ao nome de usuário para se autenticar? → A: Senha
  definida pelo usuário.

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

### User Story 2 - Recuperar anotações por significado (Priority: P2)

Como usuário autenticado, quero procurar minhas anotações por relevância semântica para encontrar
conteúdo relacionado à minha intenção mesmo quando não uso as mesmas palavras do texto original.

**Why this priority**: A recuperação semântica oferece o primeiro benefício específico de RAG e pode
ser validada antes da geração conversacional.

**Independent Test**: Pode ser testada cadastrando anotações com temas conhecidos e fazendo consultas
semanticamente equivalentes sem correspondência textual exata, verificando relevância e isolamento.

**Acceptance Scenarios**:

1. **Given** que o usuário possui anotações preparadas para recuperação, **When** consulta um conceito
   usando termos diferentes dos textos originais, **Then** o sistema retorna suas anotações mais
   semanticamente relevantes.
2. **Given** que outro usuário possui uma anotação altamente relevante para a consulta, **When** o
   usuário autenticado pesquisa, **Then** a anotação do outro usuário não é retornada nem influencia o
   resultado.
3. **Given** que uma anotação foi criada ou atualizada e persistida, **When** sua preparação semântica
   estiver em andamento, **Then** o sistema indica esse estado e disponibiliza o conteúdo atual para
   buscas e respostas em até 30 segundos.
4. **Given** uma consulta sem anotações próprias suficientemente relacionadas, **When** a recuperação
   é realizada, **Then** o sistema informa que não encontrou conteúdo pertinente, sem inserir dados de
   outros usuários.

---

### User Story 3 - Consultar anotações pelo chatbot (Priority: P3)

Como usuário autenticado, quero fazer perguntas em linguagem natural e receber respostas baseadas nas
minhas anotações, identificando as fontes utilizadas, para consultar meu conhecimento pessoal com
confiança.

**Why this priority**: Esta história entrega o fluxo RAG completo sobre a base segura de gerenciamento
e recuperação semântica.

**Independent Test**: Pode ser testada com um conjunto controlado de anotações, perguntas cujas
respostas estejam ou não no corpus e verificação das fontes apresentadas e do isolamento por usuário.

**Acceptance Scenarios**:

1. **Given** anotações próprias relevantes, **When** o usuário faz uma pergunta em linguagem natural,
   **Then** o sistema recupera apenas suas anotações, usa-as como contexto e produz uma resposta
   fundamentada nesse contexto.
2. **Given** que uma resposta utiliza anotações recuperadas, **When** a resposta é apresentada,
   **Then** o usuário consegue identificar quais de suas anotações foram usadas como fontes, sem ser
   obrigado a visualizar um score numérico de relevância.
3. **Given** que as anotações próprias não oferecem base suficiente, **When** o usuário faz uma
   pergunta, **Then** o sistema comunica a insuficiência de contexto em vez de apresentar como fato uma
   resposta não sustentada pelas anotações.
4. **Given** anotações relevantes pertencentes somente a outro usuário, **When** o usuário autenticado
   faz uma pergunta relacionada, **Then** a resposta não contém, não referencia e não é influenciada
   pelo conteúdo alheio.
5. **Given** uma sessão de uso normal, **When** o usuário interage com o chatbot, **Then** perguntas e
   respostas são apresentadas em uma interface conversacional compreensível.

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
   fornece título e conteúdo válidos, **Then** o sistema reconhece a intenção, cria e persiste a
   anotação em seu nome e apresenta uma confirmação com conteúdo identificável.
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
- Uma atualização deve invalidar o conteúdo anterior para recuperação; uma exclusão deve impedir que
  conteúdo residual apareça em buscas, contexto, respostas ou fontes.
- Falha temporária na preparação semântica deve ser informada sem perder a anotação persistida; o
  sistema deve permitir que a preparação seja retomada e não deve apresentar a versão anterior como
  se fosse o conteúdo atual.
- Consultas vazias ou sem intenção compreensível devem receber orientação e não iniciar geração sem
  contexto útil.
- Pedidos no chatbot que misturem pergunta e criação devem exigir confirmação ou esclarecimento quando
  a ação pretendida não puder ser determinada com segurança.
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
- **FR-009**: O sistema DEVE persistir imediatamente criações e atualizações, indicar quando a
  preparação semântica estiver em andamento e disponibilizar o conteúdo atual para recuperação em até
  30 segundos, refletindo também as exclusões.
- **FR-010**: O sistema DEVE permitir que um usuário autenticado recupere suas anotações por relevância
  semântica sem depender exclusivamente de correspondência textual exata.
- **FR-011**: O corpus disponível ao mecanismo de recuperação e geração DEVE conter exclusivamente
  anotações cadastradas na aplicação.
- **FR-012**: O sistema DEVE oferecer uma interface conversacional na qual o usuário autenticado possa
  enviar perguntas e visualizar respostas em linguagem natural.
- **FR-013**: Para cada pergunta do chatbot, o sistema DEVE recuperar anotações semanticamente
  relevantes pertencentes exclusivamente ao usuário autenticado e usá-las como contexto da resposta.
- **FR-014**: O sistema DEVE indicar quando o contexto recuperado for insuficiente para sustentar uma
  resposta, sem atribuir às anotações informações que elas não contenham.
- **FR-015**: Quando uma resposta usar anotações como contexto, o sistema DEVE permitir que o usuário
  identifique cada anotação utilizada como fonte; a exibição de score numérico de relevância é
  opcional.
- **FR-016**: O chatbot DEVE reconhecer solicitações explícitas de criação de anotação em linguagem
  natural, obter esclarecimento quando faltar conteúdo essencial e evitar criação quando a intenção
  não estiver suficientemente clara.
- **FR-017**: Após reconhecer uma solicitação válida de criação, o sistema DEVE criar e persistir a
  anotação para o usuário autenticado e fornecer uma confirmação identificável.
- **FR-018**: O sistema DEVE fornecer configuração e instruções de containerização suficientes para
  executar de modo reproduzível os componentes necessários ao fluxo principal.
- **FR-019**: O modelo de linguagem usado no fluxo principal DEVE poder ser executado localmente, e a
  geração principal NÃO DEVE depender obrigatoriamente de uma API externa de modelo de linguagem.
- **FR-020**: Falhas DEVEM resultar em comportamento previsível e mensagens compreensíveis, sem expor
  dados de outros usuários, informações sensíveis ou detalhes internos.
- **FR-021**: Após confirmação do usuário, o sistema DEVE excluir permanentemente a anotação e todas as
  suas representações recuperáveis, sem oferecer restauração ou lixeira.

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
  autenticado, incluindo a intenção interpretada quando houver pedido de criação.
- **Resposta conversacional**: Resultado apresentado ao usuário, fundamentado no contexto permitido e
  acompanhado das fontes utilizadas quando aplicável.
- **Fonte**: Referência identificável a uma anotação própria efetivamente utilizada como contexto de
  uma resposta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em testes de aceitação, 100% das tentativas de acesso cruzado entre usuários são negadas
  e nenhum conteúdo alheio aparece em listagens, buscas, respostas ou fontes.
- **SC-002**: Usuários concluem cadastro, autenticação e criação da primeira anotação em até 3 minutos
  em pelo menos 90% dos testes moderados, sem assistência técnica.
- **SC-003**: Todas as cinco operações de gerenciamento preservam o estado esperado após reinicialização
  em 100% dos cenários de persistência definidos.
- **SC-004**: Em um conjunto de consultas semanticamente equivalentes sem palavras-chave idênticas,
  pelo menos 85% apresentam, entre os cinco primeiros resultados, uma anotação própria julgada
  relevante pelo conjunto de teste.
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
  anotação fica disponível para busca semântica e respostas em até 30 segundos; durante o intervalo, o
  estado de preparação é visível ao usuário.

## Assumptions

- Há um único tipo de usuário final; funções administrativas e compartilhamento de anotações não fazem
  parte desta feature.
- O nome de usuário é fornecido pela pessoa no cadastro e possui uma regra de equivalência consistente,
  documentada ao usuário, para detectar conflitos de caixa, espaços ou outras variações aplicáveis.
- Recuperação semântica pode retornar nenhuma, uma ou várias anotações, conforme relevância suficiente;
  não existe obrigação de exibir score numérico.
- A resposta do chatbot deve se limitar ao que pode ser sustentado pelo corpus do usuário; conhecimento
  externo não integra o corpus nem deve ser apresentado como se viesse das anotações.
- A criação via chatbot exige título e conteúdo válidos, mas não exige que o usuário use um comando
  rígido ou uma frase específica.
- A configuração containerizada e a execução local destinam-se ao fluxo principal em ambiente
  compatível; quantidade de componentes, topologia e demais decisões são reservadas ao planejamento.
- Uploads, anexos, PDFs, DOCX, ingestão e RAG sobre documentos externos permanecem fora do escopo.
- Recuperação de credenciais, colaboração entre usuários, compartilhamento, versionamento de anotações
  e importação ou exportação não são introduzidos por esta specification. Lixeira, arquivamento e
  restauração de anotações também permanecem fora do escopo.
