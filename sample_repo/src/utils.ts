export interface User {
    username: string;
    password: string;
}

const users: User[] = [
    { username: "admin", password: "secret" },
];

export function getUser(username: string): User | undefined {
    return users.find(u => u.username === username);
}

export function formatName(user: User): string {
    return user.username.toUpperCase();
}
