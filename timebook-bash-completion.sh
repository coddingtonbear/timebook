# timebook(1) completion		-*- shell-script -*-
# Copyright 2016 Raphaël Droz <raphael.droz+floss@gmail.com>
# License: GNU GPL v3 or later

# Install: Put this file inside under the global or local (~/.bash_completion.d/completions)
# bash completions path and name this file "t".

_t()
{
    local cur prev words cword cmd
    _init_completion || return

    case "$prev" in
        alter|running)
            return 0
            ;;

        list|out) # no other argument than options
            COMPREPLY=( $( compgen -W "$(t $prev --help|_parse_help -)" -- "$cur" ) )
            return 0
            ;;

        switch|display|now|in)
            # all takes a timesheet or options as arguments
            COMPREPLY=( $( compgen -W "$(t list --simple)" -- "$cur" ) )
            COMPREPLY+=( $( compgen -W "$(t $prev --help|_parse_help -)" -- "$cur" ) )
            return 0
            ;;

        kill)
            COMPREPLY=( $( compgen -W "$(t list --simple)" -- "$cur" ) )
            return 0
            ;;

        --config|-C|--timebook|-b)
            _filedir
            return 0
            ;;

        # display
        -f|--format)
            COMPREPLY=( $( compgen -W "plain csv" -- "$cur" ) ) 
            return 0
            ;;
        --start|-s|--end|-e)
            return 0 # dates
            ;;

        # in
        --switch) # -s) TODO: conflict with display -s
            COMPREPLY=( $( compgen -W "$(t list --simple)" -- "$cur" ) )
            return 0
            ;;
    esac

    if [[ "$cur" == -* ]]; then
        cmd="${words[1]}"
        if [[ $cmd =~ ^alter|running|list|out|switch|display|now|kill$ ]]; then
            COMPREPLY=( $( compgen -W '$(t $prev --help|_parse_help -)' -- "$cur" ) )
        elif [[ -z "$cmd" || $cmd == $1 || $cmd =~ ^-- ]]; then
            COMPREPLY=( $( compgen -W '$(_parse_help $1 --help)' -- "$cur" ) )
        else : # dunno
        fi

        # completion --xxx= don't add extra-space
        if (( "${#COMPREPLY[*]}" == 1 )) && [[ "${COMPREPLY[0]}" =~ =$ ]]; then
            compopt -o nospace;
        fi
        return 0
    fi

    # main completion
    COMPREPLY=( $( compgen -W 'alter backend display in kill list nonw out running switch' -- "$cur" ) )
    COMPREPLY+=( $( compgen -W "$(_parse_help $1)" -- "$cur" ) )


    return 0
} &&
complete -F _t t

# Local variables:
# mode: shell-script
# sh-basic-offset: 4
# sh-indent-comment: t
# indent-tabs-mode: nil
# End:
# ex: ts=4 sw=4 et filetype=sh
