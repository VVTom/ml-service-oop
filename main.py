from datetime import datetime


class User:
    def __init__(self, user_id, user_login, password_hash):
        self._role: str = "user"
        self.user_id: int = user_id
        self.user_login: str = user_login
        self._password_hash: str = password_hash
        self.balance = Balance()


class Balance:
    def __init__(self):
        self._balance: int = 0

    def credit_balance(self, tokens: int):
        if tokens <= 0:
            raise ValueError("Сумма пополнения должна быть больше нуля")
        self._balance += tokens

    def debit_balance(self, tokens: int):
        if tokens <= 0:
            raise ValueError("Сумма списания должна быть больше нуля")

        if tokens > self._balance:
            raise ValueError(
                f"Недостаточно средств на балансе!\nСумма списания не должна превышать баланс ({self._balance})"
            )

        self._balance -= tokens

    def get_balance(self):
        return self._balance


class MlModel:
    def __init__(self, model_id, description, prediction_cost):
        self.model_id = model_id
        self.description = description
        self.prediction_cost = prediction_cost

    def prediction(self, data):
        raise NotImplementedError


class FAQNavigatorModel(MlModel):
    def __init__(self, model_id: int):
        super().__init__(
            model_id,
            description="Семантический помощник по базе знаний",
            prediction_cost=5,
        )

    def prediction(self, data):
        predictions = []
        for question in data:
            answer = f"Ответ на Ваш запрос {question}: [ответ модели]"
            predictions.append(answer)

        return predictions


class Transaction:
    def __init__(self, transaction_id, user: User, amount: int):
        if amount <= 0:
            raise ValueError("Сумма транзакции должна быть больше нуля")

        self.transaction_id: int = transaction_id
        self.user: User = user
        self.amount = amount
        self.transaction_datetime = datetime.now()
        self.is_applied: bool = False

    def apply(self):
        raise NotImplementedError


class CreditTransaction(Transaction):
    def __init__(self, transaction_id, user: User, amount: int):
        super().__init__(transaction_id, user, amount)
        self.type_transaction = "Credit"

    def apply(self):
        if self.is_applied:
            raise ValueError("Транзакция уже была выполнена")

        self.user.balance.credit_balance(self.amount)
        self.is_applied = True
        return f"Счет пополнен на {self.amount}"


class DebitTransaction(Transaction):
    def __init__(
        self,
        transaction_id,
        user: User,
        amount: int,
        ml_task: "MlTask",
    ):
        super().__init__(transaction_id, user, amount)
        self.type_transaction = "Debit"
        self.ml_task: "MlTask" = ml_task

    def apply(self):
        if self.is_applied:
            raise ValueError("Транзакция уже была выполнена")

        self.user.balance.debit_balance(self.amount)
        self.is_applied = True

        return f"Со счета списано {self.amount} за задачу {self.ml_task.task_id}"


class PredictionResult:
    def __init__(self, task, predictions, invalid_data):
        self.task = task
        self.predictions = predictions
        self.invalid_data = invalid_data
        self.created_at = datetime.now()


class MlTask:
    def __init__(
        self,
        task_id,
        user: User,
        user_data,
        model: MlModel,
    ):
        self.task_id = task_id
        self.created_time = datetime.now()
        self.user: User = user
        self.user_data: list = user_data
        self.model: MlModel = model
        self.transaction = None
        self.result = None
        self.status: str = "Waiting for a task..."

    def preprocessing_data(self):
        valid_data = []
        not_valid_data = []

        for row in self.user_data:
            if isinstance(row, str) and row.strip():
                valid_data.append(row)
            else:
                not_valid_data.append(row)

        return (valid_data, not_valid_data)

    def run(self):
        if self.status == "Completed":
            raise ValueError("Задача уже выполнена!")

        self.status = "Preprocessing data..."
        print(self.status)

        valid_data, not_valid_data = self.preprocessing_data()
        if len(valid_data) == 0:
            raise ValueError("Нет валидных данных для предсказания")

        user_balance = self.user.balance.get_balance()
        valid_predict_cost = len(valid_data) * self.model.prediction_cost

        if valid_predict_cost > user_balance:
            raise ValueError(
                f"Недостаточно токенов на балансе!\n"
                f"Для решения Вашего запроса необходимо {valid_predict_cost} токенов.\n"
                f"Ваш баланс: ({user_balance})"
            )
        self.status = "Processing..."
        print(self.status)

        valid_prediction = self.model.prediction(valid_data)

        self.transaction = DebitTransaction(
            transaction_id=self.task_id,
            user=self.user,
            amount=valid_predict_cost,
            ml_task=self,
        )
        self.transaction.apply()

        self.result = PredictionResult(
            task=self,
            predictions=valid_prediction,
            invalid_data=not_valid_data,
        )

        self.status = "Completed"
        print(self.status)
        return self.result


# test
if __name__ == "__main__":
    user = User(
        user_id=1,
        user_login="vladimir",
        password_hash="test_hash",
    )

    credit_transaction = CreditTransaction(
        transaction_id=1,
        user=user,
        amount=20,
    )

    print(credit_transaction.apply())
    print("Баланс после пополнения:", user.balance.get_balance())

    model = FAQNavigatorModel(model_id=1)

    task = MlTask(
        task_id=1,
        user=user,
        user_data=[
            "Как изменить пароль?",
            "",
            "Как обратиться в поддержку?",
            None,
        ],
        model=model,
    )

    result = task.run()

    print("Предсказания:", result.predictions)
    print("Ошибочные строки:", result.invalid_data)
    print("Статус задачи:", task.status)
    print("Баланс после выполнения:", user.balance.get_balance())

    try:
        task.run()
    except ValueError as error:
        print("Повторный запуск:", error)
