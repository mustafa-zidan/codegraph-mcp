import { getUser } from "./utils";

export function login(username: string, password: string): boolean {
    const user = getUser(username);
    if (!user) {
        return false;
    }
    return user.password === password;
}

export class AuthService {
    authenticate(username: string, password: string): boolean {
        return login(username, password);
    }
}
