"""Tests for the voice mail system. Run: python test_voice_mail.py"""

import contextlib
import io
import unittest

from voice_mail import (CONNECTED, INCORRECT, PROMPT, RECORDING, Connection,
                        MailSystem, Message, MessageQueue, Telephone)


def call(system, *lines):
    """Run a whole call with scripted input; return (connection, spoken)."""
    phone = Telephone(io.StringIO("\n".join(lines) + "\n"))
    connection = Connection(system, phone)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        phone.run(connection)
    return connection, out.getvalue().splitlines()


class MessageTests(unittest.TestCase):
    def test_get_and_set(self):
        message = Message("hello")
        self.assertEqual(message.get(), "hello")
        message.set("bye")
        self.assertEqual(message.get(), "bye")

    def test_queue_is_first_in_first_out(self):
        queue = MessageQueue()
        queue.addMessage(Message("one"))
        queue.addMessage(Message("two"))
        self.assertEqual(queue.size(), 2)
        self.assertEqual(queue.removeMessage().get(), "one")
        self.assertEqual(queue.removeMessage().get(), "two")
        self.assertEqual(queue.size(), 0)


class ReachAnExtensionTests(unittest.TestCase):
    def test_prompt_then_greeting_for_a_real_extension(self):
        connection, spoken = call(MailSystem(20), "1", "3", "#")
        self.assertEqual(spoken[0], PROMPT)
        self.assertEqual(spoken[1], "You have reached mailbox 13. "
                                    "Please leave a message now")
        # No hang up yet, so the caller is still at the mailbox.
        self.assertEqual(connection._state, RECORDING)

    def test_state_is_recording_once_the_mailbox_is_reached(self):
        system = MailSystem(5)
        phone = Telephone(io.StringIO(""))
        connection = Connection(system, phone)
        with contextlib.redirect_stdout(io.StringIO()):
            connection.connect()
            for key in "2#":
                connection.dial(key)
        self.assertEqual(connection._state, RECORDING)
        self.assertIs(connection._currentMailbox, system.findMailbox("2"))

    def test_unknown_extension_is_refused_and_can_be_retried(self):
        _, spoken = call(MailSystem(5), "9", "9", "#", "3", "#")
        self.assertEqual(spoken[1], INCORRECT)
        self.assertIn("mailbox 3", spoken[2])

    def test_find_mailbox(self):
        system = MailSystem(3)
        self.assertIsNotNone(system.findMailbox("2"))
        self.assertIsNone(system.findMailbox("3"))
        self.assertIsNone(system.findMailbox(""))
        self.assertIsNone(system.findMailbox("x"))


class LeaveAMessageTests(unittest.TestCase):
    def test_message_is_placed_in_the_mailbox_on_hangup(self):
        system = MailSystem(5)
        call(system, "2", "#", "Please call me back", "H")
        queue = system.findMailbox("2")._newMessages
        self.assertEqual(queue.size(), 1)
        self.assertEqual(queue.removeMessage().get(), "Please call me back")

    def test_other_mailboxes_are_untouched(self):
        system = MailSystem(5)
        call(system, "2", "#", "hi", "H")
        self.assertEqual(system.findMailbox("3")._newMessages.size(), 0)

    def test_messages_queue_up_in_order(self):
        system = MailSystem(5)
        call(system, "1", "#", "first", "H")
        call(system, "1", "#", "second", "H")
        queue = system.findMailbox("1")._newMessages
        self.assertEqual([queue.removeMessage().get(),
                          queue.removeMessage().get()], ["first", "second"])

    def test_hanging_up_before_a_mailbox_is_reached_leaves_nothing(self):
        system = MailSystem(5)
        call(system, "2", "H")
        self.assertEqual(system.findMailbox("2")._newMessages.size(), 0)

    def test_speaking_before_a_mailbox_is_reached_is_not_recorded(self):
        system = MailSystem(5)
        call(system, "hello?", "2", "#", "real message", "H")
        queue = system.findMailbox("2")._newMessages
        self.assertEqual(queue.removeMessage().get(), "real message")

    def test_the_connection_is_reset_after_hanging_up(self):
        connection, _ = call(MailSystem(5), "2", "#", "hi", "H")
        self.assertEqual(connection._state, CONNECTED)
        self.assertIsNone(connection._currentMailbox)
        self.assertEqual(connection._currentRecording, "")
        self.assertEqual(connection._accumulatedKeys, "")

    def test_a_message_is_not_saved_until_the_caller_hangs_up(self):
        system = MailSystem(5)
        call(system, "2", "#", "unfinished")        # input ends, no H
        self.assertEqual(system.findMailbox("2")._newMessages.size(), 0)


if __name__ == "__main__":
    unittest.main()
