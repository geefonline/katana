#!/usr/bin/env python3
from typing import Generator, Tuple, List, Any, Dict
import requests

from katana.repl.ctf import CTFProvider, Challenge, User, AuthenticationError


class Provider(CTFProvider):
    def _authenticate(self, username: str, password: str) -> None:

        # Build a requests session object
        s = requests.session()

        # Grab a nonce
        r = s.get(f"{self.url}/login")
        if r.status_code != 200:
            raise AuthenticationError(
                f"Received status code {r.status_code} from login"
            )

        # Parse the nonce
        nonce = r.text.split('name="nonce" value="')[1].split('"')[0]

        # Attempt authentication
        r = s.post(
            f"{self.url}/login",
            data={"name": username, "password": password, "nonce": nonce},
        )
        if r.status_code != 200:
            raise AuthenticationError(
                f"received status code {r.status_code} from login"
            )

        # Grab the CSRF token
        self.csrf_token = r.text.split('csrf_nonce = "')[1].split('"')[0]

        # Save requests session
        self.session = s

    @property
    def me(self) -> User:

        # Get user profile
        r = self.session.get(f"{self.url}/api/v1/users/me")
        if r.status_code != 200:
            raise RuntimeError(f"failed to retrieve profile")

        data = r.json()["data"]
        user: User = User(
            name=data["name"],
            score=data["score"],
            ident=str(data["id"]),
            team=data["team"] if "team" in data else None,
            solves=[],
        )

        # Get user solves
        r = self.session.get(f"{self.url}/api/v1/users/me/solves")
        if r.status_code != 200:
            raise RuntimeError("failed to retrieve solves")

        # Extract solve data
        data = r.json()["data"]
        for solve in data:
            user.solves.append(
                Challenge(
                    title=solve["challenge"]["name"],
                    value=solve["challenge"]["value"],
                    ident=str(solve["challenge_id"]),
                    provider=self,
                    tags=[solve["challenge"]["category"]],
                    solved=True,
                )
            )

        return user

    @property
    def challenges(self) -> Generator[Challenge, None, None]:

        # Request the list of challenges
        r = self.session.get(f"{self.url}/api/v1/challenges")
        if r.status_code != 200:
            raise RuntimeError("failed to retrieve challenges")

        # Extract json data
        data = r.json()["data"]

        # Grab self
        me = self.me

        # Iterate over challenges
        for c in data:
            challenge = Challenge(
                title=c["name"],
                value=c["value"],
                ident=str(c["id"]),
                provider=self,
                tags=[c["category"]] + c["tags"],
            )
            if challenge.ident in [solve.ident for solve in me.solves]:
                challenge.solved = True
            yield challenge

        return

    @property
    def users(self) -> Generator[User, None, None]:

        # Request the scoreboard, which lists all users
        r = self.session.get(f"{self.url}/api/v1/scoreboard")
        if r.status_code != 200:
            raise RuntimeError("failed to get scoreboard")

        # Extract data
        data = r.json()["data"]

        # Yield all users
        for u in data:
            yield User(
                name=u["name"],
                score=u["score"],
                ident=u["account_id"],
                team=u["team"] if "team" in u else None,
            )

        return

    def scoreboard(self, localize: str = None, count=10) -> Dict[int, User]:

        # Request the scoreboard, which lists all users
        r = self.session.get(f"{self.url}/api/v1/scoreboard")
        if r.status_code != 200:
            raise RuntimeError("failed to get scoreboard")

        # Extract data
        data = r.json()["data"]

        # Assume we are starting at the top
        start = 0

        if localize is not None:
            for pos, u in enumerate(data):
                if u["name"] == localize:
                    start = pos
                    break

        # Ideal world, grab this section of the scoreboard
        start -= int(count / 2)
        end = start + count

        # Account for under or overflow
        if start < 0:
            end -= start
            start = 0
        if end >= len(data):
            start -= end - len(data)
            end = len(data)
        if start < 0:
            start = 0

        return {
            (pos + start): User(
                name=u["name"],
                score=u["score"],
                ident=str(u["account_id"]),
                team=u["team"] if "team" in u else None,
            )
            for pos, u in enumerate(data[start:end])
        }

    def get_challenge(self, ident: int) -> Challenge:

        # Request challenge details
        r = self.session.get(f"{self.url}/api/v1/challenges/{ident}")
        if r.status_code != 200:
            raise RuntimeError("failed to get challenge details")

        # Extract data
        data = r.json()["data"]

        # Build challenge structure
        challenge = Challenge(
            title=data["name"],
            value=data["value"],
            ident=str(data["id"]),
            provider=self,
            description=data["description"],
            files={
                f.split("?")[0].split("/")[-1]: f"{self.url}{f}" for f in data["files"]
            },
            tags=[data["category"]] + data["tags"],
        )

        # Set solved flag
        if challenge.ident in [c.ident for c in self.me.solves]:
            challenge.solved = True

        # Return challenge structure
        return challenge

    def submit(self, challenge: Challenge, flag: str) -> Tuple[bool, int]:

        # Attempt to submit flag
        r = self.session.post(
            f"{self.url}/api/v1/challenges/attempt",
            json={"challenge_id": challenge.ident, "submission": flag},
            headers={"CSRF-Token": self.csrf_token},
        )
        if r.status_code != 200:
            raise RuntimeError("failed to submit flag")

        # Check if it was right
        data = r.json()["data"]
        if data["status"] != "incorrect":
            challenge.solved = True
            return True, 1
        else:
            return False, 1