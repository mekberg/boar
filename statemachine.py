

class GenericStateMachine:
    def __init__(self):
        self.states = set()
        self.events = set()

        # (state, event) -> state
        self.transitions = {}

        # ((state, event) -> handler
        self.transition_handlers = {}

        # state -> [callable, ...]
        self.enter_handlers = {}

        # state -> [callable, ...]
        self.exit_handlers = {}

        self.state = None

        self.started = False
        self.event_queue = []

    def start(self, state):
        assert not self.started
        self.started = True
        assert state in self.states
        self.state = state

    def add_event(self, event):
        assert not self.started
        assert event not in self.events
        assert type(event) == str
        self.events.add(event)

    def add_state(self, state):
        assert not self.started
        assert state not in self.states
        assert type(state) == str
        self.states.add(state)

    def add_transition(self, from_state, event, to_state):
        assert not self.started
        assert from_state in self.states
        assert to_state in self.states
        assert event in self.events
        key = (from_state, event)
        assert key not in self.transitions
        self.transitions[key] = to_state

    def add_transition_handler(self, from_state, event, to_state, handler):
        assert callable(handler)
        key = (from_state, event)
        assert self.transitions[key] == to_state
        if key not in self.transition_handlers:
            self.transition_handlers[key] = []
        self.transition_handlers[key].append(handler)

    def add_enter_handler(self, state, handler):
        assert not self.started
        assert callable(handler)
        if state not in self.enter_handlers:
            self.enter_handlers[state] = []
        self.enter_handlers[state].append(handler)

    def add_exit_handler(self, state, handler):
        assert not self.started
        assert callable(handler)
        if state not in self.exit_handlers:
            self.exit_handlers[state] = []
        self.exit_handlers[state].append(handler)

    def dispatch(self, event, **kwargs):
        assert self.started
        assert event in self.events
        kwargs['event'] = event
        self.event_queue.append((event, kwargs))
        self.execute_until_idle()

    def execute_once(self):
        assert self.started
        assert self.event_queue
        event, args = self.event_queue.pop(0)
        new_state = self.transitions.get((self.state, event), None)
        args_to_print = dict(args)
        #if "block_data" in args_to_print: del args_to_print['block_data']
        #print "Transitioning: %s + (%s %s) -> %s" % (self.state, event, args_to_print, new_state)
        assert new_state, "No transistion defined for %s + %s" % (self.state, event)
        for handler in self.exit_handlers.get(self.state, []):
            handler(**args)
        for handler in self.transition_handlers.get((self.state, event), []):
            handler(**args)
        self.state = new_state
        for handler in self.enter_handlers.get(new_state, []):
            handler(**args)

    def get_state(self):
        return self.state

    def execute_until_idle(self):
        while self.event_queue:
            self.execute_once()

def say(s):
    print s

def main():
    gsm = GenericStateMachine()
    gsm.add_state("a")
    gsm.add_state("b")
    gsm.add_event("EV")
    gsm.add_transition("a", "EV", "b")
    gsm.add_transition_handler("a", "EV", "b", lambda args: say("Transition to b"))
    gsm.add_enter_handler("b", lambda args: say("Enter b"))

    gsm.start("a")
    gsm.dispatch("EV")
    gsm.dispatch("EV")
    gsm.execute_once()
    gsm.execute_until_idle()
    print gsm.state

if __name__ == "__main__":
    main()




