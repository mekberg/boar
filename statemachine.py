

class GenericStateMachine:
    def __init__(self):
        self.states = set()
        self.events = set()

        # (state, event) -> state
        self.transitions = {} 
        
        # state -> [callable, ...]
        self.enter_handlers = {}

        # state -> [callable, ...]
        self.exit_handlers = {}

        self.current_state = None

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
        assert from_state in self.states
        assert to_state in self.states
        assert event in self.events
        key = (from_state, event)
        assert key not in self.transitions
        self.transitions[key] = to_state

    def push_event(self, event, args = None):
        assert self.started
        assert event in self.events
        self.event_queue.append((event, args))

    def add_enter_handler(self, state, handler):
        assert not self.started
        if state not in self.enter_handlers:
            self.enter_handlers[state] = []
        self.enter_handlers[state].append(handler)

    def add_exit_handler(self, state, handler):
        assert not self.started
        if state not in self.exit_handlers:
            self.exit_handlers[state] = []
        self.exit_handlers[state].append(handler)        

    def execute_once(self):
        assert self.started
        assert self.event_queue
        event, args = self.event_queue.pop(0)
        new_state = self.transitions.get((self.state, event), None)
        assert new_state, "No transistion defined for %s + %s" % (self.state, event)
        for handler in self.exit_handlers.get(new_state, []):
            handler(args)
        self.state = new_state
        for handler in self.enter_handlers.get(new_state, []):
            handler(args)

def say(s):
    print s

def main():
    gsm = GenericStateMachine()
    gsm.add_state("a")
    gsm.add_state("b")
    gsm.add_event("EV")
    gsm.add_transition("a", "EV", "b")
    gsm.add_enter_handler("b", lambda args: say("Enter b"))
    gsm.start("a")
    gsm.push_event("EV")
    gsm.execute_once()
    print gsm.state
    

main()


        
        
