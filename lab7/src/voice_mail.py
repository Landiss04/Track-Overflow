"""Voice mail system: the classes of the class diagram, nothing more.

Telephone, Connection, MailSystem, Mailbox, MessageQueue and Message,
with the attributes and operations the diagram shows. The two use cases
it carries out are Reach an Extension and Leave a Message.

Run ``python voice_mail.py`` to try it by hand: type digits and ``#`` to
dial an extension, any other text to speak, and ``H`` to hang up.
"""

import sys

#: Connection states. The state diagram has more; these two are all the
#: two use cases need.
CONNECTED = 1
RECORDING = 2

PROMPT = "Enter mailbox number followed by #"
INCORRECT = "Incorrect mailbox number. Try again."
KEYS = "0123456789#"
HANGUP = "H"


class Message:
    """One recorded message."""

    def __init__(self, text):
        self._messageText = text

    def get(self):
        return self._messageText

    def set(self, text):
        self._messageText = text


class MessageQueue:
    """Messages in first-in, first-out order."""

    def __init__(self):
        self._messageList = []

    def addMessage(self, message):
        self._messageList.append(message)

    def removeMessage(self):
        return self._messageList.pop(0)

    def size(self):
        return len(self._messageList)


class Mailbox:
    """A greeting and two queues: new messages and saved ones."""

    def __init__(self, greeting):
        self._greeting = greeting
        self._newMessages = MessageQueue()
        self._savedMessages = MessageQueue()

    def getGreeting(self):
        return self._greeting

    def addMessage(self, message):
        self._newMessages.addMessage(message)


class MailSystem:
    """Holds the mailboxes. A mailbox's extension is its position."""

    def __init__(self, mailbox_count):
        self._mailboxes = [
            Mailbox(f"You have reached mailbox {number}. "
                    "Please leave a message now")
            for number in range(mailbox_count)
        ]

    def findMailbox(self, extension):
        """Return the mailbox for an extension, or None if there is none."""
        if not extension.isdigit():
            return None
        number = int(extension)
        if number >= len(self._mailboxes):
            return None
        return self._mailboxes[number]


class Telephone:
    """Takes input from the user and speaks output."""

    def __init__(self, scanner):
        # Anything that yields one line at a time: stdin, a StringIO...
        self._scanner = scanner

    def speak(self, text):
        print(text)

    def run(self, connection):
        """Pass each input line to the connection until hang up.

        A single 0-9 or # is a key, an H is hanging up, anything else is
        the user speaking.
        """
        connection.connect()
        for line in self._scanner:
            line = line.strip()
            if line == HANGUP:
                connection.hangup()
                return
            if len(line) == 1 and line in KEYS:
                connection.dial(line)
            else:
                connection.record(line)


class Connection:
    """One call: which state it is in and what it has collected so far."""

    def __init__(self, system, phone):
        self._system = system
        self._phone = phone
        self._currentMailbox = None
        self._currentRecording = ""
        self._state = CONNECTED
        self._accumulatedKeys = ""

    def connect(self):
        """Start a call and speak the prompt."""
        self.resetConnection()
        self._phone.speak(PROMPT)

    def resetConnection(self):
        self._currentMailbox = None
        self._currentRecording = ""
        self._state = CONNECTED
        self._accumulatedKeys = ""

    def dial(self, key):
        """Collect extension digits; # finds the mailbox."""
        if self._state != CONNECTED:
            return
        if key != "#":
            self._accumulatedKeys += key
            return
        mailbox = self._system.findMailbox(self._accumulatedKeys)
        if mailbox is None:
            self._accumulatedKeys = ""
            self._phone.speak(INCORRECT)
            return
        self._currentMailbox = mailbox
        self._state = RECORDING
        self._phone.speak(mailbox.getGreeting())

    def record(self, text):
        """Add what the caller said to the recording."""
        if self._state == RECORDING:
            self._currentRecording += text

    def hangup(self):
        """End the call; a recording is kept in the mailbox reached."""
        if self._state == RECORDING:
            self._currentMailbox.addMessage(Message(self._currentRecording))
        self.resetConnection()


if __name__ == "__main__":
    phone = Telephone(sys.stdin)
    phone.run(Connection(MailSystem(10), phone))
