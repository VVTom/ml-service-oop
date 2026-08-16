import streamlit as st

from api_client import (
    check_api,
    create_batch_prediction,
    create_prediction,
    get_balance,
    get_prediction_history,
    get_transaction_history,
    login_user,
    register_user,
    top_up_balance,
    wait_for_prediction,
)


st.set_page_config(
    page_title="ML Service",
    page_icon="🤖",
    layout="wide",
)


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "login" not in st.session_state:
    st.session_state.login = None

if "password" not in st.session_state:
    st.session_state.password = None

if "last_prediction" not in st.session_state:
    st.session_state.last_prediction = None

if "batch_results" not in st.session_state:
    st.session_state.batch_results = []

if "batch_errors" not in st.session_state:
    st.session_state.batch_errors = []


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

st.sidebar.title("ML Service")

if check_api():
    st.sidebar.success("Backend доступен")
else:
    st.sidebar.error("Backend недоступен")


if st.session_state.authenticated:
    st.sidebar.write(f"Пользователь: **{st.session_state.login}**")

    page = st.sidebar.radio(
        "Навигация",
        [
            "Главная",
            "Личный кабинет",
            "ML-анализ",
            "История",
        ],
    )

    if st.sidebar.button("Выйти"):
        st.session_state.authenticated = False
        st.session_state.login = None
        st.session_state.password = None
        st.session_state.last_prediction = None
        st.session_state.batch_results = []
        st.session_state.batch_errors = []

        st.rerun()

else:
    page = "Главная"


# ---------------------------------------------------------------------
# Главная страница
# ---------------------------------------------------------------------

if page == "Главная":
    st.title("🤖 ML Service")

    st.write("Web-интерфейс сервиса для анализа тональности текста.")

    st.write(
        "Сервис позволяет отправлять текст "
        "на обработку ML-моделью, получать результат, "
        "управлять балансом и просматривать историю "
        "операций."
    )

    st.subheader("Как работает сервис")

    st.markdown(
        """
1. Пользователь регистрируется и входит в систему.
2. Пополняет баланс.
3. Отправляет текст на анализ.
4. Backend создаёт ML-задачу.
5. Задача отправляется через RabbitMQ.
6. Один из ML-воркеров выполняет предсказание.
7. Результат сохраняется в системе.
8. Пользователь видит результат и списание кредитов.
"""
    )

    st.subheader("ML-модель")

    st.write(
        "Для определения тональности текста "
        "используется модель "
        "`cointegrated/rubert-tiny-sentiment-balanced`."
    )

    st.write("Возможные классы: `positive`, `neutral`, `negative`.")


# ---------------------------------------------------------------------
# Регистрация и авторизация
# ---------------------------------------------------------------------

if not st.session_state.authenticated:
    st.divider()

    st.subheader("Вход в личный кабинет")

    tab_login, tab_register = st.tabs(
        [
            "Вход",
            "Регистрация",
        ]
    )

    with tab_login:
        login = st.text_input(
            "Логин",
            key="login_input",
        )

        password = st.text_input(
            "Пароль",
            type="password",
            key="password_input",
        )

        if st.button(
            "Войти",
            key="login_button",
        ):
            success, response = login_user(
                login=login,
                password=password,
            )

            if success:
                st.session_state.authenticated = True
                st.session_state.login = login
                st.session_state.password = password

                st.rerun()

            else:
                st.error(
                    response.get(
                        "detail",
                        "Ошибка авторизации",
                    )
                )

    with tab_register:
        new_login = st.text_input(
            "Новый логин",
            key="register_login",
        )

        new_password = st.text_input(
            "Новый пароль",
            type="password",
            key="register_password",
        )

        if st.button(
            "Зарегистрироваться",
            key="register_button",
        ):
            success, response = register_user(
                login=new_login,
                password=new_password,
            )

            if success:
                st.success("Пользователь зарегистрирован. Теперь можно войти.")

            else:
                st.error(
                    response.get(
                        "detail",
                        "Ошибка регистрации",
                    )
                )


# ---------------------------------------------------------------------
# Личный кабинет
# ---------------------------------------------------------------------

if st.session_state.authenticated and page == "Личный кабинет":
    st.title("👤 Личный кабинет")

    st.write(f"Вы вошли как: **{st.session_state.login}**")

    balance_success, balance_response = get_balance(
        login=st.session_state.login,
        password=st.session_state.password,
    )

    if balance_success:
        st.metric(
            "Текущий баланс",
            f"{balance_response['balance']} кредитов",
        )

        try:
            current_balance = float(balance_response["balance"])

            if current_balance <= 0:
                st.warning("На балансе нет средств для выполнения ML-запросов.")

        except (TypeError, ValueError):
            pass

    else:
        st.error(
            balance_response.get(
                "detail",
                "Не удалось получить баланс",
            )
        )

    st.divider()

    st.subheader("Пополнение баланса")

    top_up_amount = st.number_input(
        "Сумма пополнения",
        min_value=1.0,
        value=10.0,
        step=10.0,
    )

    if st.button(
        "Пополнить баланс",
        key="top_up_button",
    ):
        success, response = top_up_balance(
            login=st.session_state.login,
            password=st.session_state.password,
            amount=top_up_amount,
        )

        if success:
            st.success(f"Баланс пополнен до {response['balance']} кредитов")

            st.rerun()

        else:
            st.error(
                response.get(
                    "detail",
                    "Ошибка пополнения баланса",
                )
            )


# ---------------------------------------------------------------------
# ML-анализ
# ---------------------------------------------------------------------

if st.session_state.authenticated and page == "ML-анализ":
    st.title("🤖 ML-анализ")

    balance_success, balance_response = get_balance(
        login=st.session_state.login,
        password=st.session_state.password,
    )

    if balance_success:
        st.metric(
            "Текущий баланс",
            f"{balance_response['balance']} кредитов",
        )

    single_tab, batch_tab = st.tabs(
        [
            "Один текст",
            "Несколько строк",
        ]
    )

    # -----------------------------------------------------------------
    # Одиночное предсказание
    # -----------------------------------------------------------------

    with single_tab:
        st.subheader("Анализ одного текста")

        prediction_text = st.text_area(
            "Введите текст",
            placeholder=("Например: Мне очень понравился этот сервис"),
            height=150,
            key="single_prediction_text",
        )

        if st.button(
            "Получить предсказание",
            key="single_prediction_button",
        ):
            if not prediction_text.strip():
                st.warning("Введите текст для анализа")

            else:
                success, response = create_prediction(
                    login=st.session_state.login,
                    password=st.session_state.password,
                    text=prediction_text.strip(),
                )

                if not success:
                    st.error(
                        response.get(
                            "detail",
                            "Не удалось создать ML-задачу",
                        )
                    )

                else:
                    task_id = response["task_id"]

                    st.info(f"Задача {task_id} отправлена на обработку")

                    with st.spinner("ML-модель обрабатывает текст..."):
                        (
                            prediction_success,
                            prediction,
                        ) = wait_for_prediction(
                            login=st.session_state.login,
                            password=st.session_state.password,
                            task_id=task_id,
                        )

                    if prediction_success:
                        st.session_state.last_prediction = prediction

                        st.rerun()

                    else:
                        st.error(
                            prediction.get(
                                "detail",
                                "Ошибка выполнения ML-задачи",
                            )
                        )

        if st.session_state.last_prediction is not None:
            prediction = st.session_state.last_prediction

            result = prediction["prediction"]

            st.success("Предсказание выполнено")

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Тональность",
                    result["sentiment"],
                )

                st.metric(
                    "Уверенность модели",
                    f"{result['score']:.2%}",
                )

            with col2:
                st.metric(
                    "Списано кредитов",
                    prediction["charged"],
                )

                st.write(f"Worker: `{result['worker_id']}`")

                st.write(f"Статус: `{prediction['status']}`")

    # -----------------------------------------------------------------
    # Пакетная обработка
    # -----------------------------------------------------------------

    with batch_tab:
        st.subheader("Анализ нескольких строк")

        st.write(
            "Введите несколько текстов. "
            "Каждая строка будет проверена backend "
            "и обработана как отдельный ML-запрос."
        )

        st.info(
            "Некорректные строки не останавливают "
            "обработку всего пакета. "
            "Backend возвращает их отдельно, "
            "а корректные строки передаются ML-воркерам."
        )

        batch_text = st.text_area(
            "Данные",
            placeholder=(
                "Мне понравился сервис\n"
                "\n"
                "Это ужасный продукт\n"
                "Обычный нейтральный текст"
            ),
            height=220,
            key="batch_prediction_text",
        )

        if st.button(
            "Обработать строки",
            key="batch_prediction_button",
        ):
            st.session_state.batch_results = []
            st.session_state.batch_errors = []

            rows = batch_text.split("\n")

            success, response = create_batch_prediction(
                login=st.session_state.login,
                password=st.session_state.password,
                rows=rows,
            )

            if not success:
                st.error(
                    response.get(
                        "detail",
                        "Не удалось создать пакет ML-задач",
                    )
                )

            else:
                accepted = response.get(
                    "accepted",
                    [],
                )

                invalid_rows = response.get(
                    "invalid_rows",
                    [],
                )

                for invalid_row in invalid_rows:
                    st.session_state.batch_errors.append(
                        {
                            "Строка": invalid_row["row"],
                            "Данные": invalid_row["value"],
                            "Ошибка": invalid_row["error"],
                        }
                    )

                if accepted:
                    progress_bar = st.progress(0)

                    total_tasks = len(accepted)

                    with st.spinner("ML-модель обрабатывает корректные строки..."):
                        for index, item in enumerate(
                            accepted,
                            start=1,
                        ):
                            row_number = item["row"]
                            task_id = item["task_id"]

                            (
                                prediction_success,
                                prediction,
                            ) = wait_for_prediction(
                                login=(st.session_state.login),
                                password=(st.session_state.password),
                                task_id=task_id,
                            )

                            if prediction_success:
                                result = prediction["prediction"]

                                original_text = ""

                                if 1 <= row_number <= len(rows):
                                    original_text = rows[row_number - 1]

                                st.session_state.batch_results.append(
                                    {
                                        "Строка": row_number,
                                        "Текст": original_text,
                                        "Результат": (result["sentiment"]),
                                        "Уверенность": round(
                                            result["score"],
                                            4,
                                        ),
                                        "Списано": (prediction["charged"]),
                                        "Статус": (prediction["status"]),
                                        "Worker": (result["worker_id"]),
                                    }
                                )

                            else:
                                st.session_state.batch_errors.append(
                                    {
                                        "Строка": row_number,
                                        "Данные": (
                                            rows[row_number - 1]
                                            if (1 <= row_number <= len(rows))
                                            else ""
                                        ),
                                        "Ошибка": prediction.get(
                                            "detail",
                                            "Ошибка ML-задачи",
                                        ),
                                    }
                                )

                            progress_bar.progress(index / total_tasks)

                st.rerun()

        if st.session_state.batch_results:
            st.success("Корректные строки обработаны")

            st.dataframe(
                st.session_state.batch_results,
                width="stretch",
                hide_index=True,
            )

        if st.session_state.batch_errors:
            st.warning("Некоторые строки были отклонены")

            st.dataframe(
                st.session_state.batch_errors,
                width="stretch",
                hide_index=True,
            )


# ---------------------------------------------------------------------
# История
# ---------------------------------------------------------------------

if st.session_state.authenticated and page == "История":
    st.title("📜 История")

    transactions_tab, predictions_tab = st.tabs(
        [
            "Транзакции",
            "Предсказания",
        ]
    )

    with transactions_tab:
        (
            transactions_success,
            transactions,
        ) = get_transaction_history(
            login=st.session_state.login,
            password=st.session_state.password,
        )

        if transactions_success:
            if transactions:
                st.dataframe(
                    transactions,
                    width="stretch",
                    hide_index=True,
                )

            else:
                st.info("История транзакций пока пуста")

        else:
            st.error(
                transactions.get(
                    "detail",
                    "Не удалось получить историю транзакций",
                )
            )

    with predictions_tab:
        (
            predictions_success,
            predictions,
        ) = get_prediction_history(
            login=st.session_state.login,
            password=st.session_state.password,
        )

        if predictions_success:
            if predictions:
                st.dataframe(
                    predictions,
                    width="stretch",
                    hide_index=True,
                )

            else:
                st.info("История предсказаний пока пуста")

        else:
            st.error(
                predictions.get(
                    "detail",
                    "Не удалось получить историю предсказаний",
                )
            )
