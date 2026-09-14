; wrapper so the tune can be played by a .sid player (verification only)
* = $1000
        jmp musinit             ; $1000 init
        jmp mplay               ; $1003 play
!source "music.inc"
