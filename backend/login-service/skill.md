## 🤖 AI Code Generation Rules (공통 지침)

본 프로젝트는 Claude Code와 Antigravity CLI(agy)를 혼용하여 개발하므로, 두 AI는 코드 생성 시 다음 규칙을 엄격히 준수해야 한다.

1. **상호 컨텍스트 공유 및 동기화**
   - 각 AI는 작업 시작 전 반드시 최신 `skill.md`와 `기능명세서`를 완벽히 숙지한 후 코드를 작성한다.
   - 코드 수정 시 기존 구현된 타 서비스(FastAPI ↔ gRPC 등)의 인터페이스를 깨뜨리지 않는 방어적 코딩을 수행한다.

2. **기술 스택 및 아키텍처 제약 조건**
   - **Back-end:** Python, FastAPI
   - **Connect-Database**: PostgreSQL, MongoDB, Redis(Valkey 전환 고려)
   - **내부 통신:** 무조건 gRPC와 `.proto` 기반 자동 컴파일 스텁 활용 (Crawler, ElasticSearch, Monitoring, Logging 연동).

3. **환경 격리 및 의존성 관리**
   - 로컬 환경에 직접 패키지를 설치하지 말고, 반드시 Dockerfile 빌드 및 파이프라인 컴파일 환경을 기준으로 코드를 자동 생성한다.

4. **코드 컨벤션 및 보안 (Code Convention & Security)**
   - **보안:** API Key, DB Password 등 민감한 정보는 절대 코드 내에 하드코딩하지 않으며, 반드시 `.env` 형태의 환경변수를 통해 안전하게 호출한다.
   - **에러 핸들링:** 예외 처리(`try-except`) 없이 불안정한 코드를 작성하는 것을 금지하며, API 에러 응답 시 프론트엔드와 사전에 합의된 표준 JSON 포맷을 반환한다.
   - **구조화:** 비즈니스 로직과 라우터, 데이터베이스 모델을 단일 파일에 섞지 말고, 적절한 디렉토리 구조(`routers/`, `services/`, `models/` 등)로 분리하여 작성한다.

[Backend 개발을 위한 정의]

이 문서는 Backend 개발을 위한 정의를 다룬다. 본인 파트는 Backend 개발에만 몰두하면 되며, 프론트엔드 개발과 관련된 내용은 다루지 않는다. 또한, Backend 개발에 필요한 기술 스택과 데이터베이스 사용에 대한 정의를 포함한다.

데이터베이스의 경우, 데이터팀에서 직접 다루며, Backend 개발자는 데이터팀에서 제공하는 데이터를 활용해 API로 뿌려 클라이언트에게 전달하는 역할을 수행한다. 따라서 Backend 개발자는 인덱스 정의 등을 포함해 데이터베이스를 직접 다루지 않으며, 데이터팀에서 제공하는 데이터를 활용하여 API를 개발하는 역할에 집중한다. 단, Backend Software에서 처리를 위해 직접 Database로 접근하여 다루는 것은 가능하다.

1. 언어는 다음을 사용한다. - Python
2. 외부 통신을 위해 FastAPI를 사용한다.
3. 정형 데이터베이스는 PostgreSQL을 사용하며, 비정형 데이터베이스는 MongoDB를 사용한다. 개발 시에는 Primary로만 통신을 진행하고, 이후 Replica를 진행해 읽기는 Secondary에서 진행한다.
4. 임시 데이터(캐싱 데이터)는 Redis를 사용하되, 추후 라이선스 문제에 따라 Valkey로 변경될 수 있다. 기본적으로 로그인 세션도 이 곳에서 저장한다. 단, 모바일 애플리케이션 세션은 예외적으로 PostgreSQL에 로그인 세션을 저장하도록 한다.
5. 내부 서비스 간 통신은 마이크로서비스(MSA) 환경에 최적화된 초고속 gRPC를 사용하며, 프론트엔드 및 외부 클라이언트와의 통신은 FastAPI 기반의 REST API를 사용해 역할을 엄격하게 분리한다.
6. 검색 서비스는 ElasticSearch를 사용하며, PostgreSQL과 MongoDB에서 데이터를 가져와 ElasticSearch에 색인(Indexing)하여 검색 서비스를 제공한다. 또한, ElasticSearch는 데이터팀에서 직접 다루며, Backend 개발자는 데이터팀에서 제공하는 검색 API를 활용하여 클라이언트에게 검색 결과를 전달하는 역할을 수행한다.

[내부 통신]
gRPC 이용 시 서로 간 통신을 위해 Protocol Buffers (.proto)를 인터페이스 정의 언어(IDL)로 사용하며, 서비스 간 규약 불일치(Version Mismatch) 장애를 방지하기 위해 .proto 파일들은 단일 Git 레포지토리(또는 Submodule)를 통해 중앙 집중식으로 형상 관리를 수행한다. 또한, 해당 규약 파일의 파이썬 스텁(Stub) 코드 변환은 도커(Docker) 빌드 및 CI/CD 파이프라인 내에서 자동화하여 휴먼 에러를 원천 차단한다. gRPC 통신은 monitoring, Logging, Crawler Server, ElasticSearch Server에서 사용될 예정이다.

[로그인 정책]

로그인은 기본적으로 Social Login을 사용하며, Administrator에 속한 계정에 대해서만 일반적인 ID와 Password를 사용하며, Administrator 로그인은 반드시 Cloudflare의 Turnstile bot check를 통과해야 한다. Social Login은 Google, Kakao, Naver, Apple을 지원하며, 기본적으로는 한국인이 가장 많이 쓰는 Naver를 우선적으로 배치, 다음 Kakao를 배치한다. Google과 Apple은 그 다음 순서로 배치한다. Social Login을 사용하지 않는 경우, Administrator 계정에 한해 ID와 Password를 사용하여 로그인할 수 있다.
참고사항으로, Apple 로그인의 경우 App Store Guideline 제 4.8.1에 따라, Apple 로그인을 제공하는 경우 반드시 Apple 로그인을 제공해야 한다. 따라서, Apple 로그인을 제공할 수 밖에 없다.

[기능명세서 안내]

기능 명세서는 Backend에 어떤 경로, 그리고 어떤 값이 들어오면 어떤 값이 나가는지에 대한 정의를 다룬다. 기능 명세서는 Backend 개발자가 API를 개발할 때 참고하는 문서로, Frontend 개발자와의 협업을 위해 작성된다.
다만, 개발 도중에 변화할 수 있는 부분이 존재하면 반드시 Frontend 개발자, 그리고 Data Team과 협의하에 변경해야 한다.

