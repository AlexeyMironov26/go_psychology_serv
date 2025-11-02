package main

import (
	"log"
	"os"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

func startResponse(bt *tgbotapi.BotAPI, upd *tgbotapi.Update) {
	msg := tgbotapi.NewMessage(upd.Message.Chat.ID, "Здравствуйте, вы попали в бот Службы Психологической Поддержки Московского Технического Университета Связи и Информатики")
	bt.Send(msg)
}

func main() {
	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	if botToken == "" {
		log.Panic("TELEGRAM_BOT_TOKEN эта переменная окружения не существует, пожалуйста, добавьте её")
	}
	bot, err := tgbotapi.NewBotAPI()
	if err != nil {
		log.Panic(err)
	}

	bot.Debug = true
	log.Printf("Авторизация в телеграме бота под никнэймом: %s прошла успешно", bot.Self.UserName)

	lastProcessedId := 0 //use this last id from db (it being saved there after end of any session)
	u := tgbotapi.NewUpdate(lastProcessedId)
	u.Timeout = 60
	updates := bot.GetUpdatesChan(u)

	for update := range updates {
		go func(updt tgbotapi.Update) {
			if updt.Message != nil {
				if updt.Message.IsCommand() {
					switch updt.Message.Command() {
					case "start":
						startResponse(bot, &updt)
					default:
						msg := tgbotapi.NewMessage(updt.Message.Chat.ID, "Вы ввели несуществующую команду, попробуйте ещё раз")
						bot.Send(msg)
					}
				}

			}
		}(update)
	}
}
