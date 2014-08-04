#:DEFINE person Ixokai

@create My Thing

@set thing=commands



&test thing=
    $hello:
        @pemit %#=Hi how are you!;
        @pemit %#=This is line two.;
        @pemit %#=
"Hmm                                        "
"                                           "
"            THIS IS MIDDLEISH"
" "
" "
    ; @pemit %#=
        The end.


think
" "
"                              What's up?           WHAT?"

&test2 thing=
    $goodbye *:
        @swi %0=
            dog,{
                @pemit %#=Bye dog!
            },
            cat,{
                @pemit %#=Bye cat!
            };
        @pemit %#=Done!

think hmm.

&something thing=$something:
    @pemit %#=
        Hello, person.

#:SEARCH stdlib Standard Library; stdlib
