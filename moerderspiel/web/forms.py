import datetime

from wtforms import Form, StringField, validators
from wtforms.fields.choices import SelectField, SelectMultipleField
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.fields.simple import PasswordField, TextAreaField

from moerderspiel import constants
from moerderspiel.db import Game


class AddPlayerForm(Form):
    form_id = "add-player"

    name = StringField('Spielername',
                       [validators.Length(max=constants.MAX_PLAYER_NAME_LENGTH)],
                       id=form_id,
                       description="""
                        Der Spielername muss innerhalb des Spiels eindeutig sein.
                        Bitte trage hier den Namen ein, der auf deinem Namensschild steht (sofern vorhanden).
                        Er wird auf den Auftragszetteln stehen.
                        """)
    group = StringField('Gruppe',
                        [validators.optional(), validators.Length(max=constants.MAX_GROUP_NAME_LENGTH)],
                        description="""
                        Wenn du mit einer Gruppe von Menschen teilnimmst, die du bereits kennst (z.B. von deiner Schule
                        oder Uni), trage hier den Namen der Gruppe/Uni/etc. ein.
                        Das bedeutet nicht, dass ihr ein Team bildet!
                        Das Spiel wird aber vermeiden, dir als ersten Auftrag jemanden aus deiner eigenen Gruppe zu
                        geben.
                        """)
    email = StringField('E-Mail-Adresse',
                        [validators.optional(), validators.Email(check_deliverability=True)],
                        filters=[lambda s: s if s is None else str.strip(s)],
                        description="""
                        Du kannst dir optional deine Mordaufträge per E-Mail zuschicken lassen.
                        """)
    password = PasswordField('Passwort',
                             [validators.EqualTo('password')],
                             description="""
                             Du kannst optional ein Passwort angeben, um vor Spielstart die Teilname an den 
                             verschiedenen Kreisen und Multispielen zu änder und nach Spielstart deine Aufträge 
                             einzusehen.
                             Gib das Passwort nicht an andere Mitspieler weiter.
                             """)

    circle_sets = SelectMultipleField('Kreis-Sets',
                         description="An welchen Kreis-sets willst du Teilnehmen? Wenn du das Feld leer lässt, wirst du in allen Kreisen eingertagen.")

    def __init__(self, game: Game, *args, **kwargs: object):
        super().__init__(*args, **kwargs)
        if game.circles:
            self.circle_sets.choices = list(set([(c.set, c.set) for c in game.circles if c.set]))



class PlayerLoginForm(Form):
    form_id = "login-player"

    name = StringField('Spielername',
                       [validators.Length(max=constants.MAX_PLAYER_NAME_LENGTH)],
                       id=form_id)
    password = PasswordField('Passwort',
                             [validators.EqualTo('password')])


class CreateGameForm(Form):
    form_id = "create-game"

    game_id = StringField('Eindeutige Spiel-ID',
                          [validators.Length(max=constants.MAX_GAME_ID_LENGTH)],
                          id=form_id,
                          description="""
                     Die Spiel-ID muss eindeutig sein und darf nur Kleinbuchstaben und Zahlen enthalten.
                     """)
    title = StringField('Titel des Spiels',
                        [validators.Length(max=constants.MAX_GAME_TITLE_LENGTH)],
                        description="""
                       Der Titel des Spiels wird auf den Auftragszetteln und der Übersichtsseite verwendet.
                       """)
    template = SelectField('Spielvorlage',
                           description="""
                            Die Spielvorlage gibt die Beschreibung und Regeln des Spiels vor.
                            Du kannst diese später anpassen.
                           """,
                           choices=[
                               ('offline', 'Einfaches Offline-Spiel'),
                               ('hybrid', 'Hybrides Online-Spiel'),
                               ('paperless', 'Papierloses Spiel')
                           ])
    password = PasswordField('Passwort',
                             [validators.EqualTo('password')],
                             description="""
                             Das Passwort brauchst Du um das Spiel zu administrieren.
                             Gib das Passwort nicht an Mitspieler weiter.
                             """)
    confirm_password = PasswordField('Passwort bestätigen')


class AddCircleForm(Form):
    form_id = "add-circle"

    name = StringField('Name des Kreises',
                       [validators.Length(max=constants.MAX_CIRCLE_NAME_LENGTH)],
                       id=form_id,
                       description="""
                       Der Name muss innerhalb des Spiels eindeutig sein.
                       """)

    set = StringField('Kreis-Set',
                      [validators.optional(), validators.Length(max=constants.MAX_CIRCLE_SET_NAME_LENGTH)],
                      description="""
                      Ein "Set" fasst in einem Multispiel mehrere Kreise zusammen. Falls alle Spieler in allen Kreisen
                      spielen, lasse dieses Feld leer.
                      """)


class GameMasterLoginForm(Form):
    form_id = "gamemaster-login"

    password = PasswordField('Passwort',
                             description="""
                             Das Gamemaster-Passwort wird beim Erstellen des Spiels gesetzt und kann aktuell leider
                             nicht zurückgesetzt werden.
                             """)


class RecordMurderForm(Form):
    form_id = "record-murder"

    killer = SelectField('Mörder',
                         description="Wer hat gemordet? (Normalerweise du selbst)")

    victim = SelectField('Opfer',
                         description="Wer wurde ermordet?")

    circle = SelectField('Kreis',
                         description="In welchem Kreis ist der Mord passiert?")

    when = DateTimeLocalField('Zeitpunkt',
                              description="Wann ist der Mord passiert?")

    mission_code = StringField('Auftrags-Code',
                               description="Der Code des Auftrags, der gerade erledigt wurde.")

    description = TextAreaField('Kreative Tatbeschreibung',
                                [validators.Length(max=constants.MAX_MURDER_DESCRIPTION_LENGTH)],
                                description="""
                                Beschreibe kurz, wie der Mord passiert ist. Kreative Ausschmückungen sind erwünscht.
                                """)

    def __init__(self, game: Game, *args, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.killer.choices = [(p.name, p.name) for p in game.players]
        self.victim.choices = [(p.name, p.name) for p in game.players]
        self.circle.choices = [(c.name, c.name) for c in game.circles]
        self.when.default = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M')
