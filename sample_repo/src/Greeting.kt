package com.example.sample

import kotlin.io.println

class Greeter {
    fun greet(name: String): String {
        return name.uppercase()
    }
}

fun main() {
    println(Greeter().greet("world"))
}
